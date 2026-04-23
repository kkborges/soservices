#!/usr/bin/env python3
"""
Validates relative Markdown links inside docs/*.md.

Rules:
- Only checks links of the form [text](target).
- Ignores absolute URLs (http/https/mailto), anchors (#...), and empty targets.
- For relative file links, resolves relative to the Markdown file directory.

Exit codes:
 0: all good
 2: broken links found
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def is_ignored(target: str) -> bool:
    t = target.strip()
    if not t:
        return True
    if t.startswith("#"):
        return True
    lower = t.lower()
    if lower.startswith(("http://", "https://", "mailto:")):
        return True
    return False


def normalize_target(target: str) -> str:
    # Strip optional title: (path "Title")
    # Keep simplest form; enough for our docs.
    t = target.strip()
    if " " in t and not t.startswith(("..", ".", "/")):
        # for safety, only split titles on typical cases
        t = t.split(" ", 1)[0].strip()
    # Drop query/hash
    t = t.split("#", 1)[0].split("?", 1)[0].strip()
    return t


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        print("docs/ not found", file=sys.stderr)
        return 0

    broken: list[str] = []
    for md_path in sorted(docs_dir.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            broken.append(f"{md_path}: failed to read: {exc}")
            continue

        for raw in LINK_RE.findall(text):
            if is_ignored(raw):
                continue
            target = normalize_target(raw)
            if not target or is_ignored(target):
                continue
            # Ignore code links (like `./foo`) that are not meant as links
            if target.startswith("`") and target.endswith("`"):
                continue
            # Absolute-from-repo root: (/docs/...) treat as repo-root anchored.
            if target.startswith("/"):
                resolved = repo_root / target.lstrip("/")
            else:
                resolved = (md_path.parent / target).resolve()

            if not resolved.exists():
                broken.append(f"{md_path.relative_to(repo_root)} -> {target}")

    if broken:
        print("Broken docs links:")
        for item in broken:
            print(f"- {item}")
        return 2

    print("Docs links OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

