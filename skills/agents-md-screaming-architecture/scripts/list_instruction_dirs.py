#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


DEFAULT_PRUNE_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".DS_Store",
}


def iter_dirs(root: Path, max_depth: int, include_hidden: bool) -> list[Path]:
    root = root.resolve()
    results: list[Path] = [root]

    for current_dir, dirnames, _filenames in os.walk(root):
        current_path = Path(current_dir)
        rel = current_path.relative_to(root)
        depth = 0 if rel == Path(".") else len(rel.parts)

        if depth >= max_depth:
            dirnames[:] = []
            continue

        pruned: list[str] = []
        for name in dirnames:
            if name in DEFAULT_PRUNE_NAMES:
                continue
            if not include_hidden and name.startswith("."):
                continue
            pruned.append(name)
        dirnames[:] = pruned

        for name in dirnames:
            results.append(current_path / name)

    return sorted(set(results))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List candidate directories for Codex instruction files (AGENTS.md/.agents.md)."
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Repository root to scan (absolute or relative).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Max directory depth to include (root=0). Default: 3.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden directories (names starting with '.').",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"--root must be an existing directory: {root}")

    dirs = iter_dirs(root=root, max_depth=max(0, args.max_depth), include_hidden=args.include_hidden)
    for path in dirs:
        rel = path.resolve().relative_to(root.resolve())
        print("." if rel == Path(".") else rel.as_posix())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

