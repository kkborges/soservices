#!/usr/bin/env python3
"""
Fix mTLS bootstrap/config for the dev integrations gateway running as a container.

Why this exists:
- In dev, it's common to redeploy the API/edge stack and end up with a gateway that
  has mTLS disabled or stale CA/certs.
- When mTLS is required, the gateway must use the platform-issued CA + client cert/key.
- The bootstrap endpoint may be served with a self-signed chain in dev. We therefore
  allow *insecure TLS* only for the bootstrap call (TOFU). All operational traffic
  still uses mTLS with CA pinning.

This script:
1) Reads /etc/las/gateway.conf from a given container (docker exec).
2) Calls the platform bootstrap endpoint to obtain CA/client/server cert bundle.
3) Uploads files to the remote host via SFTP, then docker-cp into the container.
4) Forces mtls.enabled=true in gateway.conf and restarts the container.

Usage (from your workstation/repo root):
  $env:LAS_SSH_PASSWORD='***'
  python scripts/ops/fix_gateway_integrations_mtls.py ^
    --host 192.168.0.108 --user kleber ^
    --container las-gateway-integrations ^
    --bootstrap-base https://192.168.0.108:8443

Notes:
- Requires paramiko on the local machine.
- Remote user must have permission to run docker (docker group).
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import ssl
import sys
import tempfile
from pathlib import Path
from urllib import parse, request

import paramiko


def _connect(host: str, user: str, port: int, password: str | None) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=host,
        username=user,
        port=port,
        password=password,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
    )
    return ssh


def _exec(ssh: paramiko.SSHClient, cmd: str) -> tuple[int, bytes, bytes]:
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=False)
    out_b = stdout.read()
    err_b = stderr.read()
    return stdout.channel.recv_exit_status(), out_b, err_b


def _must(status: int, out_b: bytes, err_b: bytes, context: str) -> bytes:
    if status != 0:
        raise SystemExit(
            f"{context} failed (exit={status}).\nSTDOUT:\n{out_b.decode(errors='ignore')}\nSTDERR:\n{err_b.decode(errors='ignore')}"
        )
    return out_b


def _read_gateway_conf(ssh: paramiko.SSHClient, container: str) -> str:
    code, out_b, err_b = _exec(ssh, f"docker exec -i {container} cat /etc/las/gateway.conf")
    return _must(code, out_b, err_b, "Read gateway.conf").decode("utf-8", errors="replace")


def _write_remote_files_via_sftp(ssh: paramiko.SSHClient, remote_dir: str, files: dict[str, bytes]) -> None:
    code, out_b, err_b = _exec(ssh, f"mkdir -p {remote_dir}")
    _must(code, out_b, err_b, "mkdir remote_dir")
    sftp = ssh.open_sftp()
    try:
        for name, data in files.items():
            remote_path = f"{remote_dir}/{name}"
            with sftp.open(remote_path, "wb") as f:
                f.write(data)
    finally:
        sftp.close()


def _bootstrap_mtls(
    *,
    bootstrap_base: str,
    token: str,
    hostname: str,
    public_endpoint: str,
) -> dict:
    base = bootstrap_base.rstrip("/")
    url = f"{base}/api/v1/agents/bootstrap/mtls?{parse.urlencode({'hostname': hostname, 'public_endpoint': public_endpoint})}"
    req = request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    # Dev: allow bootstrap over insecure TLS. Operational traffic uses pinned CA.
    ctx = ssl._create_unverified_context()
    with request.urlopen(req, timeout=30, context=ctx) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _render_gateway_conf(original: str) -> str:
    p = configparser.ConfigParser()
    p.read_string(original)
    if not p.has_section("mtls"):
        p.add_section("mtls")
    p.set("mtls", "enabled", "true")
    # Keep required=true if present, but do not force it here.
    buf = []
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        p.write(tmp)
        tmp_path = Path(tmp.name)
    try:
        return tmp_path.read_text(encoding="utf-8")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--password-env", default="LAS_SSH_PASSWORD")
    ap.add_argument("--container", default="las-gateway-integrations")
    ap.add_argument("--bootstrap-base", required=True, help="Base URL for mTLS edge, e.g. https://192.168.0.108:8443")
    ap.add_argument(
        "--force-mtls-platform-url",
        default=None,
        help="Override mtls.platform_url in gateway.conf (useful in dev when DNS does not resolve inside Docker).",
    )
    ap.add_argument("--hostname", default=None, help="Optional override for certificate DNS name")
    ap.add_argument("--public-endpoint", default=None, help="Optional override for gateway public endpoint")
    args = ap.parse_args()

    password = os.environ.get(args.password_env) or None
    ssh = _connect(args.host, args.user, args.port, password)
    try:
        conf_text = _read_gateway_conf(ssh, args.container)
        conf = configparser.ConfigParser()
        conf.read_string(conf_text)
        token = conf.get("las", "gateway_token", fallback="").strip()
        if not token:
            raise SystemExit("gateway_token not found in gateway.conf")

        hostname = args.hostname or conf.get("las", "public_endpoint", fallback="").strip()
        if hostname.startswith("https://"):
            hostname = hostname.removeprefix("https://")
        hostname = hostname.split(":")[0].strip() or None

        # Best-effort fallback: remote hostname.
        if not hostname:
            code, out_b, err_b = _exec(ssh, "hostname -f 2>/dev/null || hostname")
            hostname = _must(code, out_b, err_b, "hostname").decode("utf-8", errors="ignore").strip()

        public_endpoint = args.public_endpoint or conf.get("las", "public_endpoint", fallback="").strip()
        if not public_endpoint:
            public_endpoint = f"https://{hostname}:9443"

        mtls_payload = _bootstrap_mtls(
            bootstrap_base=args.bootstrap_base,
            token=token,
            hostname=hostname,
            public_endpoint=public_endpoint,
        )

        new_conf_text = _render_gateway_conf(conf_text)
        if args.force_mtls_platform_url:
            p2 = configparser.ConfigParser()
            p2.read_string(new_conf_text)
            if not p2.has_section("mtls"):
                p2.add_section("mtls")
            p2.set("mtls", "platform_url", str(args.force_mtls_platform_url).strip())
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
                p2.write(tmp)
                tmp_path = Path(tmp.name)
            try:
                new_conf_text = tmp_path.read_text(encoding="utf-8")
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
        new_conf = new_conf_text.encode("utf-8")

        files: dict[str, bytes] = {
            "mtls-ca.pem": mtls_payload["ca_pem"].encode("ascii"),
            "mtls-client.pem": mtls_payload["client_cert_pem"].encode("ascii"),
            "mtls-client-key.pem": mtls_payload["client_key_pem"].encode("ascii"),
            "mtls-server.pem": mtls_payload.get("server_cert_pem", "").encode("ascii"),
            "mtls-server-key.pem": mtls_payload.get("server_key_pem", "").encode("ascii"),
            "gateway.conf": new_conf,
        }

        remote_tmp = "/tmp/las-mtls-fix"
        _write_remote_files_via_sftp(ssh, remote_tmp, files)

        # Copy into container and restart.
        copy_cmds = [
            f"docker cp {remote_tmp}/mtls-ca.pem {args.container}:/etc/las/mtls-ca.pem",
            f"docker cp {remote_tmp}/mtls-client.pem {args.container}:/etc/las/mtls-client.pem",
            f"docker cp {remote_tmp}/mtls-client-key.pem {args.container}:/etc/las/mtls-client-key.pem",
            f"docker cp {remote_tmp}/mtls-server.pem {args.container}:/etc/las/mtls-server.pem",
            f"docker cp {remote_tmp}/mtls-server-key.pem {args.container}:/etc/las/mtls-server-key.pem",
            f"docker cp {remote_tmp}/gateway.conf {args.container}:/etc/las/gateway.conf",
            f"docker restart {args.container}",
        ]
        for c in copy_cmds:
            code, out_b, err_b = _exec(ssh, c)
            _must(code, out_b, err_b, c)

        # Show last logs for quick validation
        code, out_b, err_b = _exec(ssh, f"docker logs --tail 40 {args.container}")
        _must(code, out_b, err_b, "docker logs")
        sys.stdout.buffer.write(out_b)
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
