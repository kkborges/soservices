#!/usr/bin/env python3
"""
Regenera os pacotes .tar.gz na raiz do repo (agents/backend/docker/docs/frontend/tests).

Motivacao:
- Mantem os bundles atualizados para distribuicao/replicacao (SaaS/on-prem).
- Evita pacotes vazios/desatualizados.

Uso:
  python scripts/build_component_archives.py
  python scripts/build_component_archives.py --out-dir .
"""

from __future__ import annotations

import argparse
import os
import tarfile
from pathlib import Path


DEFAULT_COMPONENTS: dict[str, str] = {
    "agents": "agents",
    "backend": "backend",
    "docker": "docker",
    "docs": "docs",
    "frontend": "frontend",
    "tests": "tests",
}


EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage_html",
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
}


def _should_exclude(path: Path) -> bool:
    # Exclude by any directory name in the path.
    for part in path.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    # Exclude by suffix.
    if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
        return True
    return False


def _tar_add_dir(tar: tarfile.TarFile, root_dir: Path, arc_prefix: str) -> None:
    for p in sorted(root_dir.rglob("*")):
        if _should_exclude(p):
            continue
        # Skip broken symlinks / non-existent targets (rare on Windows shares).
        try:
            st = p.lstat()
        except OSError:
            continue
        # Only add files and directories.
        if not (p.is_file() or p.is_dir()):
            continue
        rel = p.relative_to(root_dir)
        arcname = str(Path(arc_prefix) / rel)
        tar.add(str(p), arcname=arcname, recursive=False)


def build_archives(repo_root: Path, out_dir: Path, components: dict[str, str]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    built: list[Path] = []

    for name, rel_dir in components.items():
        src = repo_root / rel_dir
        if not src.exists() or not src.is_dir():
            raise SystemExit(f"Componente '{name}' nao encontrado em {src}")

        out_path = out_dir / f"{name}.tar.gz"
        # Replace atomically-ish: write temp then rename.
        tmp_path = out_dir / f".{name}.tar.gz.tmp"
        if tmp_path.exists():
            tmp_path.unlink()

        with tarfile.open(tmp_path, "w:gz", compresslevel=6) as tar:
            _tar_add_dir(tar, src, arc_prefix=rel_dir)

        if out_path.exists():
            out_path.unlink()
        tmp_path.replace(out_path)
        built.append(out_path)

    return built


def main() -> int:
    parser = argparse.ArgumentParser(description="Build component .tar.gz archives.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Caminho do repo (default: raiz do projeto).",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Diretorio de saida (default: raiz do repo).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_dir = (repo_root / args.out_dir).resolve() if args.out_dir == "." else Path(args.out_dir).resolve()

    built = build_archives(repo_root=repo_root, out_dir=out_dir, components=DEFAULT_COMPONENTS)
    for p in built:
        size = p.stat().st_size
        print(f"{p.name}: {size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

