#!/usr/bin/env python3
"""List or remove generated evidence artifacts."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="vision-in-time-output")
    parser.add_argument("--delete", action="store_true", help="Actually delete the directory.")
    args = parser.parse_args()

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f"Nothing to clean: {target}")
        return 0
    if not target.is_dir():
        raise SystemExit(f"Refusing to clean non-directory path: {target}")

    files = [p for p in target.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    print(f"{target}")
    print(f"files={len(files)} bytes={size}")

    if args.delete:
        try:
            shutil.rmtree(target)
        except OSError as error:
            print(f"deleted=false error={error}", file=sys.stderr)
            return 1
        print("deleted=true")
    else:
        print("deleted=false dry_run=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
