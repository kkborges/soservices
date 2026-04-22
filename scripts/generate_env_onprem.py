#!/usr/bin/env python3
from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path


def _replace_placeholder(text: str, key: str, placeholder: str, *, length: int) -> str:
    pattern = re.compile(rf"^({re.escape(key)})={re.escape(placeholder)}\s*$", re.M)

    def repl(_: re.Match) -> str:
        return f"{key}={secrets.token_urlsafe(length)}"

    return pattern.sub(repl, text)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: generate_env_onprem.py <example_path> <output_path>", file=sys.stderr)
        return 2
    example_path = Path(argv[1]).expanduser()
    output_path = Path(argv[2]).expanduser()

    text = example_path.read_text(encoding="utf-8", errors="replace")

    text = _replace_placeholder(text, "POSTGRES_PASSWORD", "change_me_strong", length=32)
    text = _replace_placeholder(text, "REPMGR_PASSWORD", "change_me_strong_repmgr", length=32)
    text = _replace_placeholder(text, "PGPOOL_ADMIN_PASSWORD", "change_me_strong_pgpool_admin", length=32)
    text = _replace_placeholder(text, "REDIS_PASSWORD", "change_me_strong_redis", length=32)
    text = _replace_placeholder(text, "SECRET_KEY", "change_me_to_a_64_char_random_string", length=64)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

