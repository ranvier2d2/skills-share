#!/usr/bin/env python3
"""Deterministic Flashback session handoff generator."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from adapters import get_adapter
from flashback_core import FlashbackInputs, run_flashback


def detect_runtime(runtime_arg: str) -> str:
    if runtime_arg != "auto":
        return runtime_arg

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_PROJECT_DIR"):
        return "claude"
    return "codex"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained Flashback restart prompt and run report.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "quick", "summary"],
        default="full",
        help=(
            "full = gather+consolidate+generate, "
            "quick = generate from current memory, "
            "summary = full workflow with user summary as primary accomplishments source"
        ),
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Optional human summary used as primary accomplishments source",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for memory/task discovery",
    )
    parser.add_argument(
        "--memory-dir",
        default=None,
        help="Explicit memory directory or MEMORY.md file path",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: <repo-root>/output/flashback)",
    )
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Skip clipboard copy",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run capability/discovery checks without writing files",
    )
    parser.add_argument(
        "--runtime",
        choices=["auto", "codex", "claude"],
        default="auto",
        help="Runtime adapter (auto defaults to codex unless Claude env markers are set)",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = detect_runtime(args.runtime)

    repo_root = Path(args.repo_root).expanduser().resolve()
    out_dir = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else (repo_root / "output" / "flashback").resolve()
    )

    adapter = get_adapter(runtime)
    inputs = FlashbackInputs(
        mode=args.mode,
        summary=args.summary,
        repo_root=repo_root,
        memory_dir_arg=args.memory_dir,
        out_dir=out_dir,
        disable_clipboard=args.no_clipboard,
        dry_run=args.dry_run,
    )

    try:
        if args.mode == "summary" and not args.summary:
            print("ERROR: --mode summary requires --summary.", file=sys.stderr)
            return 2
        result = run_flashback(adapter, inputs)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for line in result.summary_lines:
        print(line)

    if args.dry_run:
        print("Dry-run completed. No files were written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
