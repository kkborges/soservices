#!/usr/bin/env python3
"""
Gera os bundles de deploy em releases/:
- LAS_SAAS_DEPLOY_YYYYMMDD.tar.gz
- LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz
- LAS_INSTALLERS_YYYYMMDD.tar.gz
- LAS_PLATFORM_INSTALLER_YYYYMMDD.tar.gz

Objetivo: entregar um "kit" portavel com docker-compose/k8s/docs/scripts e instaladores,
sem depender do repo completo.
"""

from __future__ import annotations

import argparse
import os
import re
import tarfile
from datetime import datetime
from pathlib import Path


EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage_html",
    "htmlcov",
}

EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo", ".log"}


def _should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
        return True
    return False


def _add_path(tar: tarfile.TarFile, repo_root: Path, rel: str) -> None:
    src = repo_root / rel
    if not src.exists():
        raise SystemExit(f"Path nao encontrado para bundle: {src}")

    if src.is_file():
        tar.add(str(src), arcname=rel.replace("\\", "/"))
        return

    # Directory
    for p in sorted(src.rglob("*")):
        if _should_exclude(p):
            continue
        if not (p.is_file() or p.is_dir()):
            continue
        arcname = str(p.relative_to(repo_root)).replace("\\", "/")
        tar.add(str(p), arcname=arcname, recursive=False)


def _build_tar(out_path: Path, repo_root: Path, includes: list[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    with tarfile.open(tmp, "w:gz", compresslevel=6) as tar:
        for rel in includes:
            _add_path(tar, repo_root, rel)

    if out_path.exists():
        out_path.unlink()
    tmp.replace(out_path)


def _build_universal_installer_tar(
    out_path: Path,
    repo_root: Path,
    includes: list[str],
    release_bundle_paths: list[Path],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    with tarfile.open(tmp, "w:gz", compresslevel=6) as tar:
        for rel in includes:
            _add_path(tar, repo_root, rel)
        for bundle in release_bundle_paths:
            if not bundle.exists():
                raise SystemExit(f"Bundle base nao encontrado para installer universal: {bundle}")
            tar.add(str(bundle), arcname=f"bundles/{bundle.name}")

    if out_path.exists():
        out_path.unlink()
    tmp.replace(out_path)


def _date_yyyymmdd() -> str:
    # Uses local time (America/Sao_Paulo in our env)
    return datetime.now().strftime("%Y%m%d")


def _cleanup_old(releases_dir: Path, prefix: str, keep: str) -> list[Path]:
    removed: list[Path] = []
    # Match bundles like PREFIX_YYYYMMDD.tar.gz
    rx = re.compile(rf"^{re.escape(prefix)}_\d{{8}}\.tar\.gz$")
    for p in releases_dir.glob(f"{prefix}_*.tar.gz"):
        if p.name == keep:
            continue
        if rx.match(p.name):
            p.unlink(missing_ok=True)
            removed.append(p)
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="Build LAS release bundles in releases/.")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--releases-dir", default="releases")
    ap.add_argument("--date", default=os.environ.get("LAS_RELEASE_DATE", "") or _date_yyyymmdd())
    ap.add_argument("--keep-old", action="store_true", help="Nao remove bundles antigos")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    releases_dir = (repo_root / args.releases_dir).resolve()
    date = args.date
    if not re.fullmatch(r"\d{8}", date):
        raise SystemExit("--date deve ser YYYYMMDD")

    saas_name = f"LAS_SAAS_DEPLOY_{date}.tar.gz"
    onprem_name = f"LAS_ONPREM_DEPLOY_{date}.tar.gz"
    installers_name = f"LAS_INSTALLERS_{date}.tar.gz"
    platform_installer_name = f"LAS_PLATFORM_INSTALLER_{date}.tar.gz"

    # Kits de deploy (SaaS e On-premise) sao equivalentes em conteudo.
    deploy_includes = [
        "docker",
        "backend",
        "scripts",
        "k8s",
        "docs",
        "runtime",
        "deploy.py",
        "QUICK_START.md",
        "INDICE.md",
        "IMPLEMENTACAO_SERVIDOR_LAS.md",
    ]

    installers_includes = [
        "dist",
        "installer",
        "LASAgentSetup.spec",
        "LASGatewaySetup.spec",
        "las-agent-windows-x64.spec",
        "las-gateway-windows-x64.spec",
        # Linux/Windows binaries produced by backend build pipeline
        "backend/releases",
        # Core docs for installation
        "docs/PACOTES-E-INSTALADORES.md",
        "docs/SUPORTE-E-COLETA-DE-LOGS.md",
        "docs/DEPLOYMENT-CLIENTE.md",
        "docs/INSTALADOR-UNIFICADO-E-TRIAL.md",
    ]

    universal_includes = [
        "installer",
        "docs/INSTALADOR-UNIFICADO-E-TRIAL.md",
        "docs/PACOTES-E-INSTALADORES.md",
        "docs/DEPLOYMENT-CLIENTE.md",
        "docs/DEPLOYMENT-CADDY.md",
        "docs/FAILOVER-PRODUCAO.md",
    ]

    saas_path = releases_dir / saas_name
    onprem_path = releases_dir / onprem_name
    installers_path = releases_dir / installers_name
    platform_installer_path = releases_dir / platform_installer_name

    _build_tar(saas_path, repo_root, deploy_includes)
    _build_tar(onprem_path, repo_root, deploy_includes)
    _build_tar(installers_path, repo_root, installers_includes)
    _build_universal_installer_tar(
        platform_installer_path,
        repo_root,
        universal_includes,
        [saas_path, onprem_path, installers_path],
    )

    if not args.keep_old:
        _cleanup_old(releases_dir, "LAS_SAAS_DEPLOY", saas_name)
        _cleanup_old(releases_dir, "LAS_ONPREM_DEPLOY", onprem_name)
        _cleanup_old(releases_dir, "LAS_INSTALLERS", installers_name)
        _cleanup_old(releases_dir, "LAS_PLATFORM_INSTALLER", platform_installer_name)

    for p in (saas_path, onprem_path, installers_path, platform_installer_path):
        st = p.stat()
        print(f"{p.name}: {st.st_size} bytes ({datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
