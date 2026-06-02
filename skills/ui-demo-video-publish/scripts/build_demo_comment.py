#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Build a concise Linear demo comment body.')
    p.add_argument('--validated', required=True, help='What was validated')
    p.add_argument('--path-shown', required=True, help='What path was shown in the demo')
    p.add_argument('--limitation', default='', help='Known limitation or omission')
    p.add_argument('--attachment-note', default='Demo video attached.', help='Opening line for the comment')
    p.add_argument('--json', action='store_true', help='Emit JSON instead of plain markdown')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    lines = [
        args.attachment_note.strip(),
        f'Validated: {args.validated.strip()}',
        f'Path shown: {args.path_shown.strip()}',
    ]
    if args.limitation.strip():
        lines.append(f'Known limitation: {args.limitation.strip()}')
    body = '\n'.join(lines)
    if args.json:
        print(json.dumps({'body': body}))
    else:
        print(body)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
