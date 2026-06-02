#!/usr/bin/env python3
"""
Generate a structured research report template.

Example:
  python3 scripts/report_skeleton.py --topic "Ralph Wiggum loop" --out /tmp/research_report.md
"""

from __future__ import annotations

import argparse
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a research report skeleton.")
    parser.add_argument("--topic", required=True, help="Research topic")
    parser.add_argument("--out", required=True, help="Output markdown file")
    return parser.parse_args()


def build_template(topic: str) -> str:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"""# Research Report: {topic}

## Executive Summary
- [Add 2-3 sentence overview of the key findings and implications]

## Key Findings
### Finding 1
- [Evidence + explanation]

### Finding 2
- [Evidence + explanation]

### Finding 3
- [Evidence + explanation]

## Current State Analysis
- [Describe current status, trends, and gaps]

## Sources and Verification
- [Source 1 - note what it supports]
- [Source 2 - note what it supports]

## Implications and Recommendations
- [Actionable recommendations or next steps]

## Research Limitations
- [What is missing, uncertain, or unverified]

---
Generated: {timestamp}
"""


def main() -> int:
    args = parse_args()
    content = build_template(args.topic)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
