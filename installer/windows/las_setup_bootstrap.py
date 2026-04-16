#!/usr/bin/env python3
"""Windows bootstrap installer for LAS agent and gateway.

The executable can carry an appended JSON configuration overlay:

    <portable-exe-bytes><json-bytes><8-byte little-endian length><magic>

This allows the API to generate tenant-aware Setup.exe downloads without
rebuilding the installer for every token.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:  # pragma: no cover
    tk = None
    ttk = None
    messagebox = None

if os.name != "nt":  # pragma: no cover
    raise SystemExit("This installer is intended for Windows only.")

import winreg


OVERLAY_MAGIC = b"LASSETUPCFG1"
CREATE_NO_WINDOW = 0x08000000


@dataclass
class InstallerConfig:
    kind: str
    product_name: str
    display_name: str
    install_dir: str
    config_dir: str
    log_dir: str
    service_name: str
    setup_name: str
    payload_name: str
    artifact_path: str
    mtls_bootstrap_path: str = "/api/v1/agents/bootstrap/mtls"
    token: str = ""
    platform_url: str = "https://api.soservices.com.br"
    mtls_platform_url: str = "https://api.soservices.com.br:8443"
    role: str = "agent"
    gateway_type: str = "infra"
    gateway_urls: list[str] = field(default_factory=list)
    gateway_public_endpoint: str = ""
    expected_sha256: str = ""
    heartbeat_interval: int = 60
    metrics_interval: int = 30
    routing_refresh_interval: int = 300
    update_check_interval: int = 3600


class ProgressUI:
    def __init__(self, title: str):
        self.console_only = tk is None or ttk is None
        self.title = title
        if self.console_only:
            print(title, flush=True)
            self.root = None
            return

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("540x170")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        wrap = 500
        self.title_label = tk.Label(self.root, text=title, font=("Segoe UI", 14, "bold"))
        self.title_label.pack(padx=18, pady=(18, 8), anchor="w")

        self.status_var = tk.StringVar(value="Preparando...")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, wraplength=wrap, justify="left")
        self.status_label.pack(padx=18, pady=(0, 10), anchor="w")

        self.bar = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100, length=500)
        self.bar.pack(padx=18, pady=(0, 10))

        self.detail_var = tk.StringVar(value="")
        self.detail_label = tk.Label(self.root, textvariable=self.detail_var, wraplength=wrap, justify="left", fg="#5f6368")
        self.detail_label.pack(padx=18, anchor="w")

        self.root.update()

    def update(self, percent: int, status: str, detail: str = "") -> None:
        if self.console_only:
            print(f"[{percent:3d}%] {status} {detail}".strip(), flush=True)
            return
        self.status_var.set(status)
        self.detail_var.set(detail)
        self.bar["value"] = max(0, min(percent, 100))
        self.root.update_idletasks()
        self.root.update()

    def finish(self, status: str, detail: str = "") -> None:
        self.update(100, status, detail)

    def error(self, title: str, text: str) -> None:
        if self.console_only:
            print(f"ERROR: {title}: {text}", file=sys.stderr, flush=True)
            return
        messagebox.showerror(title, text)

    def info(self, title: str, text: str) -> None:
        if self.console_only:
            print(f"{title}: {text}", flush=True)
            return
        messagebox.showinfo(title, text)

    def close(self) -> None:
        if self.root is not None:
            self.root.destroy()


def default_kind_from_executable() -> str:
    stem = Path(sys.executable if getattr(sys, "frozen", False) else __file__).stem.lower()
    return "gateway" if "gateway" in stem else "agent"


def default_config(kind: str) -> InstallerConfig:
    if kind == "gateway":
        return InstallerConfig(
            kind="gateway",
            product_name="LAS Plataforma de Monitoramento e Observabilidade",
            display_name="LAS Gateway",
            install_dir=r"C:\LASGateway",
            config_dir=r"C:\LASGateway\config",
            log_dir=r"C:\LASGateway\logs",
            service_name="LASGateway",
            setup_name="LASGatewaySetup.exe",
            payload_name="las-gateway.exe",
            artifact_path="/api/v1/agents/artifacts/windows-gateway.exe",
            gateway_type="infra",
        )
    return InstallerConfig(
        kind="agent",
        product_name="LAS Plataforma de Monitoramento e Observabilidade",
        display_name="LAS Agent",
        install_dir=r"C:\LASAgent",
        config_dir=r"C:\LASAgent\config",
        log_dir=r"C:\LASAgent\logs",
        service_name="LASAgent",
        setup_name="LASAgentSetup.exe",
        payload_name="las-agent.exe",
        artifact_path="/api/v1/agents/artifacts/windows-agent.exe",
        role="agent",
    )


def read_embedded_overlay() -> dict:
    source = Path(sys.executable if getattr(sys, "frozen", False) else __file__)
    data = source.read_bytes()
    trailer_size = len(OVERLAY_MAGIC) + 8
    if len(data) < trailer_size:
        return {}
    trailer = data[-trailer_size:]
    if not trailer.endswith(OVERLAY_MAGIC):
        return {}
    length = int.from_bytes(trailer[:8], "little")
    if length <= 0 or length > len(data) - trailer_size:
        return {}
    raw = data[-trailer_size - length: -trailer_size]
    return json.loads(raw.decode("utf-8"))


def merge_config(base: InstallerConfig, overlay: dict) -> InstallerConfig:
    data = dict(base.__dict__)
    for key, value in overlay.items():
        if key in data and value is not None:
            data[key] = value
    if isinstance(data.get("gateway_urls"), str):
        data["gateway_urls"] = [item.strip() for item in data["gateway_urls"].split(",") if item.strip()]
    return InstallerConfig(**data)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_command(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(args)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def service_exists(name: str) -> bool:
    result = run_command(["sc.exe", "query", name], check=False)
    return result.returncode == 0


def stop_and_remove_service(name: str, nssm_path: Path | None = None) -> None:
    if not service_exists(name):
        return
    if nssm_path and nssm_path.exists():
        run_command([str(nssm_path), "stop", name], check=False)
        run_command([str(nssm_path), "remove", name, "confirm"], check=False)
    else:
        run_command(["sc.exe", "stop", name], check=False)
        run_command(["sc.exe", "delete", name], check=False)


def hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def download_file(
    url: str,
    destination: Path,
    headers: dict[str, str] | None,
    progress: Callable[[int, str], None],
    start_percent: int,
    end_percent: int,
) -> None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            total = int(response.headers.get("Content-Length", "0") or 0)
            downloaded = 0
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        ratio = downloaded / total
                        percent = int(start_percent + ((end_percent - start_percent) * ratio))
                        progress(percent, f"Baixando {destination.name} ({downloaded // 1024} KB)")
    except HTTPError as exc:
        raise RuntimeError(f"Falha ao baixar {url}: HTTP {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha ao baixar {url}: {exc.reason}") from exc
    progress(end_percent, f"Download concluido: {destination.name}")


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Falha ao chamar {url}: HTTP {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha ao chamar {url}: {exc.reason}") from exc


def detect_gateway_public_endpoint() -> str:
    host = socket.getfqdn() or socket.gethostname() or "localhost"
    host = host.strip() or "localhost"
    return f"https://{host}:9443"


def ensure_nssm(install_dir: Path, progress: Callable[[int, str], None]) -> Path:
    nssm_path = install_dir / "nssm.exe"
    if nssm_path.exists():
        return nssm_path
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "nssm.exe"
    if bundled.exists():
        shutil.copy2(bundled, nssm_path)
        progress(68, "NSSM incorporado ao instalador")
        return nssm_path
    temp_zip = Path(tempfile.gettempdir()) / "las-nssm.zip"
    temp_extract = Path(tempfile.gettempdir()) / "las-nssm"
    download_file(
        "https://nssm.cc/release/nssm-2.24.zip",
        temp_zip,
        headers=None,
        progress=progress,
        start_percent=55,
        end_percent=68,
    )
    if temp_extract.exists():
        shutil.rmtree(temp_extract, ignore_errors=True)
    with zipfile.ZipFile(temp_zip, "r") as archive:
        archive.extractall(temp_extract)
    source = temp_extract / "nssm-2.24" / "win64" / "nssm.exe"
    shutil.copy2(source, nssm_path)
    return nssm_path


def write_text_ascii(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="ascii", errors="strict")


def build_agent_config(config: InstallerConfig) -> str:
    gateway_urls = ",".join(config.gateway_urls)
    return (
        "[nexus]\n"
        f"nexus_url = {config.platform_url}\n"
        f"agent_token = {config.token}\n"
        f"role = {config.role}\n"
        f"log_dir = {config.log_dir}\n"
        f"install_dir = {config.install_dir}\n\n"
        "[intervals]\n"
        f"heartbeat_interval = {config.heartbeat_interval}\n"
        f"metrics_interval = {config.metrics_interval}\n\n"
        "[updates]\n"
        "enabled = true\n"
        f"check_interval = {config.update_check_interval}\n\n"
        "[routing]\n"
        f"gateway_urls = {gateway_urls}\n"
        f"routing_refresh_interval = {config.routing_refresh_interval}\n"
        "gateway_strategy = priority-weighted-failover\n\n"
        "[mtls]\n"
        "enabled = true\n"
        "required = true\n"
        f"platform_url = {config.mtls_platform_url}\n"
        f"ca_file = {config.config_dir}\\mtls-ca.pem\n"
        f"client_cert_file = {config.config_dir}\\mtls-client.pem\n"
        f"client_key_file = {config.config_dir}\\mtls-client-key.pem\n\n"
        "[transport]\n"
        "compress_data = true\n"
        "protect_data = true\n"
        "protection = mtls\n\n"
        "[features]\n"
        "process_monitor = true\n"
        "port_scan = true\n"
        "disk_monitor = true\n"
        "network_monitor = true\n"
        "log_collection = true\n"
        "otel_enabled = true\n"
        "ids_enabled = false\n"
    )


def build_gateway_config(config: InstallerConfig) -> str:
    return (
        "[nexus]\n"
        f"nexus_url = {config.platform_url}\n"
        f"gateway_token = {config.token}\n"
        f"type = {config.gateway_type}\n"
        "listen_host = 0.0.0.0\n"
        "listen_port = 9443\n"
        f"public_endpoint = {config.gateway_public_endpoint}\n\n"
        "[intervals]\n"
        f"heartbeat_interval = {config.heartbeat_interval}\n"
        "task_poll_interval = 20\n\n"
        "[updates]\n"
        "enabled = true\n"
        f"check_interval = {config.update_check_interval}\n\n"
        "[mtls]\n"
        "enabled = true\n"
        "required = true\n"
        f"platform_url = {config.mtls_platform_url}\n"
        f"ca_file = {config.config_dir}\\mtls-ca.pem\n"
        f"client_cert_file = {config.config_dir}\\mtls-client.pem\n"
        f"client_key_file = {config.config_dir}\\mtls-client-key.pem\n"
        f"server_cert_file = {config.config_dir}\\mtls-server.pem\n"
        f"server_key_file = {config.config_dir}\\mtls-server-key.pem\n\n"
        "[transport]\n"
        "compress_data = true\n"
        "protect_data = true\n"
        "protection = mtls\n\n"
        "[cluster]\n"
        "cluster_name = default\n"
        "priority = 100\n"
        "weight = 1\n"
        "failover_only = false\n"
        "shared_with_tenants = false\n\n"
        "[features]\n"
        "logs = true\n"
        "otel = true\n"
        "security = true\n"
        "ids = true\n"
        "network_discovery = true\n"
        "snmp = true\n"
        "syslog = true\n\n"
        "[syslog]\n"
        "enabled = true\n"
        "listen_host = 0.0.0.0\n"
        "udp_port = 514\n"
        "tcp_port = 514\n"
        "tls_port = 6514\n"
    )


def copy_self_as_uninstaller(target: Path) -> None:
    source = Path(sys.executable if getattr(sys, "frozen", False) else __file__)
    shutil.copy2(source, target)


def set_uninstall_registry(config: InstallerConfig, uninstall_path: Path) -> None:
    key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{config.service_name}"
    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, config.display_name)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "4.0.0")
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "SOServices")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, config.install_dir)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(uninstall_path))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_path}" /uninstall')
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstall_path}" /uninstall /quiet')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def remove_uninstall_registry(service_name: str) -> None:
    key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{service_name}"
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
    except FileNotFoundError:
        pass


def install(config: InstallerConfig, ui: ProgressUI) -> None:
    if not is_admin():
        raise RuntimeError("Execute o instalador como Administrador.")

    install_dir = Path(config.install_dir)
    config_dir = Path(config.config_dir)
    log_dir = Path(config.log_dir)
    payload_path = install_dir / config.payload_name
    setup_target = install_dir / config.setup_name
    config_path = config_dir / ("gateway.conf" if config.kind == "gateway" else "agent.conf")

    ui.update(5, "Preparando diretorios")
    install_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    ui.update(12, "Gravando configuracao")
    write_text_ascii(config_path, build_gateway_config(config) if config.kind == "gateway" else build_agent_config(config))

    ui.update(16, "Provisionando certificados mTLS")
    headers = {"Authorization": f"Bearer {config.token}"} if config.token else {}
    bootstrap_params = {}
    local_hostname = socket.getfqdn() or socket.gethostname()
    if local_hostname:
        bootstrap_params["hostname"] = local_hostname
    if config.kind == "gateway":
        bootstrap_params["public_endpoint"] = config.gateway_public_endpoint or detect_gateway_public_endpoint()
    mtls_url = urllib.parse.urljoin(config.platform_url.rstrip("/") + "/", config.mtls_bootstrap_path.lstrip("/"))
    if bootstrap_params:
        mtls_url = f"{mtls_url}?{urllib.parse.urlencode(bootstrap_params)}"
    mtls_bundle = fetch_json(mtls_url, headers=headers)
    config.mtls_platform_url = mtls_bundle.get("mtls_platform_url") or config.mtls_platform_url
    write_text_ascii(config_dir / "mtls-ca.pem", mtls_bundle["ca_pem"])
    write_text_ascii(config_dir / "mtls-client.pem", mtls_bundle["client_cert_pem"])
    write_text_ascii(config_dir / "mtls-client-key.pem", mtls_bundle["client_key_pem"])
    if config.kind == "gateway":
        config.gateway_public_endpoint = mtls_bundle.get("gateway_public_endpoint") or bootstrap_params["public_endpoint"]
        write_text_ascii(config_dir / "mtls-server.pem", mtls_bundle["server_cert_pem"])
        write_text_ascii(config_dir / "mtls-server-key.pem", mtls_bundle["server_key_pem"])
    write_text_ascii(config_path, build_gateway_config(config) if config.kind == "gateway" else build_agent_config(config))

    temp_payload = Path(tempfile.gettempdir()) / f"{config.service_name}-{os.getpid()}.exe"
    payload_url = urllib.parse.urljoin(config.platform_url.rstrip("/") + "/", config.artifact_path.lstrip("/"))
    download_file(payload_url, temp_payload, headers, lambda p, s: ui.update(p, s), 18, 52)

    size = temp_payload.stat().st_size
    if size < 1024 * 1024:
        raise RuntimeError(f"Executavel baixado com tamanho invalido: {size} bytes")
    if config.expected_sha256:
        current = hash_file(temp_payload)
        if current != config.expected_sha256.upper():
            raise RuntimeError(f"Hash do payload invalido. Esperado {config.expected_sha256}, obtido {current}")

    nssm_path = ensure_nssm(install_dir, lambda p, s: ui.update(p, s))

    ui.update(70, "Atualizando servico")
    stop_and_remove_service(config.service_name, nssm_path)

    if payload_path.exists():
        payload_path.unlink()
    shutil.move(str(temp_payload), payload_path)

    ui.update(78, "Copiando desinstalador")
    copy_self_as_uninstaller(setup_target)
    set_uninstall_registry(config, setup_target)

    ui.update(86, "Registrando servico")
    run_command([str(nssm_path), "install", config.service_name, str(payload_path)])
    run_command([str(nssm_path), "set", config.service_name, "AppDirectory", str(install_dir)])
    run_command([str(nssm_path), "set", config.service_name, "AppStdout", str(log_dir / ("gateway.log" if config.kind == "gateway" else "agent.log"))])
    run_command([str(nssm_path), "set", config.service_name, "AppStderr", str(log_dir / ("gateway-error.log" if config.kind == "gateway" else "agent-error.log"))])
    run_command([str(nssm_path), "set", config.service_name, "Start", "SERVICE_AUTO_START"])
    run_command([str(nssm_path), "set", config.service_name, "AppEnvironmentExtra", f"NEXUS_CONFIG={config_path}"])

    ui.update(94, "Iniciando servico")
    run_command(["sc.exe", "start", config.service_name], check=False)

    ui.finish("Instalacao concluida", f"{config.display_name} instalado em {config.install_dir}")


def uninstall(config: InstallerConfig, ui: ProgressUI, quiet: bool = False) -> None:
    if not is_admin():
        raise RuntimeError("Execute a desinstalacao como Administrador.")

    install_dir = Path(config.install_dir)
    nssm_path = install_dir / "nssm.exe"

    ui.update(10, "Parando servico")
    stop_and_remove_service(config.service_name, nssm_path if nssm_path.exists() else None)

    ui.update(35, "Removendo registro de desinstalacao")
    remove_uninstall_registry(config.service_name)

    ui.update(55, "Limpando arquivos")
    temp_script = Path(tempfile.gettempdir()) / f"las-uninstall-{config.service_name.lower()}.cmd"
    temp_script.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'rmdir /s /q "{install_dir}"\r\n'
        f'del /f /q "{temp_script}"\r\n',
        encoding="ascii",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", "start", "", "/min", str(temp_script)],
        creationflags=CREATE_NO_WINDOW,
    )
    ui.finish("Desinstalacao concluida", f"{config.display_name} removido.")
    if not quiet:
        ui.info("LAS", f"{config.display_name} removido com sucesso.")


def main() -> int:
    args = {arg.lower() for arg in sys.argv[1:]}
    quiet = "/quiet" in args or "/silent" in args or "--quiet" in args
    uninstall_mode = "/uninstall" in args or "--uninstall" in args

    kind = default_kind_from_executable()
    config = merge_config(default_config(kind), read_embedded_overlay())
    ui = ProgressUI(f"{config.display_name} Setup")

    try:
        if uninstall_mode:
            uninstall(config, ui, quiet=quiet)
        else:
            install(config, ui)
            if not quiet:
                ui.info(
                    "LAS",
                    f"{config.display_name} instalado com sucesso.\n\nServico: {config.service_name}\nDiretorio: {config.install_dir}",
                )
        return 0
    except Exception as exc:
        ui.error("Falha na instalacao", str(exc))
        return 1
    finally:
        if quiet:
            ui.close()


if __name__ == "__main__":
    raise SystemExit(main())
