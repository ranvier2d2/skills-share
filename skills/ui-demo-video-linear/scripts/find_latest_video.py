#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path

VIDEO_EXTS = {'.webm', '.mp4', '.mov', '.mkv'}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Locate the newest video artifact in a directory tree.')
    p.add_argument('--dir', required=True, help='Root directory to scan')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f'not a directory: {root}')

    candidates = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    if not candidates:
        print(json.dumps({'found': False, 'video_path': None}))
        return 0

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    mime_type, _ = mimetypes.guess_type(str(latest))
    print(json.dumps({
        'found': True,
        'video_path': str(latest),
        'size_bytes': latest.stat().st_size,
        'mtime_epoch': latest.stat().st_mtime,
        'mime_type': mime_type or 'application/octet-stream',
    }))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
