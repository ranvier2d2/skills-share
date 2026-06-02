#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Emit JSON ready for Linear attachment upload.')
    p.add_argument('--file', required=True, help='Video file to encode')
    p.add_argument('--issue', required=True, help='Linear issue id or key')
    p.add_argument('--title', default='Demo video')
    p.add_argument('--subtitle', default='Recorded UI validation artifact')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.file).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise SystemExit(f'file not found: {path}')

    mime_type, _ = mimetypes.guess_type(str(path))
    payload = {
        'issue': args.issue,
        'filename': path.name,
        'contentType': mime_type or 'application/octet-stream',
        'title': args.title,
        'subtitle': args.subtitle,
        'base64Content': base64.b64encode(path.read_bytes()).decode('ascii'),
    }
    print(json.dumps(payload))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
