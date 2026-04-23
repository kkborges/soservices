#!/usr/bin/env python3
"""
LAS Remote Ops (Paramiko)

Utility to run commands and sync a tarball to a remote Linux host via SSH.

Security notes:
- Do NOT hardcode passwords in this repository.
- Prefer SSH keys. If you must use a password, pass it via env var LAS_SSH_PASSWORD.
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
from pathlib import Path

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


def _exec(ssh: paramiko.SSHClient, command: str) -> int:
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=False)
    out_b = stdout.read()
    err_b = stderr.read()
    if out_b:
        sys.stdout.buffer.write(out_b)
        if not out_b.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
    if err_b:
        sys.stderr.buffer.write(err_b)
        if not err_b.endswith(b"\n"):
            sys.stderr.buffer.write(b"\n")
    return stdout.channel.recv_exit_status()


def _upload_and_extract(ssh: paramiko.SSHClient, src_dir: Path, remote_dir: str, exclude: list[str]) -> None:
    src_dir = src_dir.resolve()
    if not src_dir.exists():
        raise SystemExit(f"Source dir not found: {src_dir}")

    with tempfile.NamedTemporaryFile(prefix="las-sync-", suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with tarfile.open(tmp_path, "w:gz") as tar:
            for path in src_dir.rglob("*"):
                rel = path.relative_to(src_dir)
                rel_str = str(rel).replace("\\", "/")
                if any(rel_str == ex or rel_str.startswith(ex.rstrip("/") + "/") for ex in exclude):
                    continue
                tar.add(path, arcname=rel_str)

        sftp = ssh.open_sftp()
        remote_tmp = f"/tmp/{tmp_path.name}"
        sftp.put(str(tmp_path), remote_tmp)
        sftp.close()

        # Ensure target exists, then extract atomically to a temp dir and swap.
        _exec(ssh, f"set -euo pipefail; mkdir -p '{remote_dir}'; rm -rf '{remote_dir}.new'; mkdir -p '{remote_dir}.new'")
        _exec(ssh, f"set -euo pipefail; tar -xzf '{remote_tmp}' -C '{remote_dir}.new'")
        _exec(ssh, f"set -euo pipefail; rm -rf '{remote_dir}.old'; if [ -d '{remote_dir}' ]; then mv '{remote_dir}' '{remote_dir}.old'; fi; mv '{remote_dir}.new' '{remote_dir}'")
        _exec(ssh, f"rm -f '{remote_tmp}'")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--port", type=int, default=22)
    p.add_argument("--password-env", default="LAS_SSH_PASSWORD")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_exec = sub.add_parser("exec", help="Execute a command on the remote host")
    p_exec.add_argument("--cmd", dest="cmd_str", default=None, help="Command string (preferred when quoting/pipes are needed)")
    p_exec.add_argument("command", nargs=argparse.REMAINDER, help="Command tokens (fallback)")

    p_sync = sub.add_parser("sync", help="Upload a tar.gz of a directory and extract into remote dir")
    p_sync.add_argument("--src", required=True, help="Local directory")
    p_sync.add_argument("--dst", required=True, help="Remote directory")
    p_sync.add_argument("--exclude", action="append", default=[], help="Exclude path prefix relative to src (repeatable)")

    args = p.parse_args()
    password = os.environ.get(args.password_env) or None

    ssh = _connect(args.host, args.user, args.port, password)
    try:
        if args.cmd == "exec":
            command = args.cmd_str or (" ".join(args.command) if args.command else "")
            if not command.strip():
                raise SystemExit("No command provided (use exec --cmd \"...\" or provide tokens)")
            return _exec(ssh, command)
        if args.cmd == "sync":
            _upload_and_extract(ssh, Path(args.src), args.dst, args.exclude)
            return 0
        raise SystemExit(f"Unknown cmd: {args.cmd}")
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
