#!/usr/bin/env python3
"""
Search local files for a query and emit a Markdown evidence bundle.

Examples:
  python3 scripts/local_research.py --query "Ralph Wiggum" --path . --output /tmp/research_hits.md
  python3 scripts/local_research.py --query "tool loop" --path lib --regex --context 1
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from typing import Iterable, List, Tuple

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    ".tox",
    "node_modules",
    "_build",
    "deps",
    "dist",
    "build",
    ".kimojo",
    ".next",
    "vendor",
    "priv/static",
}

DEFAULT_EXCLUDE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".7z",
    ".mp4",
    ".mp3",
    ".mov",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local files for a query.")
    parser.add_argument("--query", required=True, help="Search query (literal or regex)")
    parser.add_argument("--path", default=".", help="Root path to search")
    parser.add_argument("--regex", action="store_true", help="Treat query as regex")
    parser.add_argument("--case-sensitive", action="store_true", help="Case-sensitive search")
    parser.add_argument("--context", type=int, default=2, help="Context lines around matches")
    parser.add_argument("--max-results", type=int, default=200, help="Maximum total matches")
    parser.add_argument("--max-size-kb", type=int, default=512, help="Skip files larger than this")
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable)",
    )
    parser.add_argument(
        "--exclude-ext",
        action="append",
        default=[],
        help="File extension to exclude (repeatable)",
    )
    parser.add_argument("--output", help="Write markdown output to this path")
    return parser.parse_args()


def is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            chunk = handle.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def iter_files(root: str, exclude_dirs: set[str], exclude_exts: set[str]) -> Iterable[str]:
    if os.path.isfile(root):
        yield root
        return

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in exclude_exts:
                continue
            yield os.path.join(dirpath, filename)


def compile_pattern(query: str, regex: bool, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    if regex:
        return re.compile(query, flags)
    return re.compile(re.escape(query), flags)


def find_matches(
    path: str,
    pattern: re.Pattern[str],
    max_size_bytes: int,
) -> List[Tuple[int, str]]:
    try:
        if os.path.getsize(path) > max_size_bytes:
            return []
    except OSError:
        return []

    if is_binary(path):
        return []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return []

    matches: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            matches.append((idx, line.rstrip("\n")))
    return matches


def render_context(lines: List[str], line_no: int, context: int) -> str:
    start = max(1, line_no - context)
    end = min(len(lines), line_no + context)
    rendered = []
    for idx in range(start, end + 1):
        prefix = ">" if idx == line_no else " "
        rendered.append(f"{prefix} {idx:4d} | {lines[idx - 1].rstrip()}".rstrip())
    return "\n".join(rendered)


def load_lines(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.readlines()
    except OSError:
        return []


def build_report(
    query: str,
    root: str,
    regex: bool,
    case_sensitive: bool,
    context: int,
    matches_by_file: List[Tuple[str, List[Tuple[int, str]]]],
) -> str:
    total_matches = sum(len(matches) for _path, matches in matches_by_file)
    total_files = sum(1 for _path, matches in matches_by_file if matches)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("# Local Research Hits")
    lines.append("")
    lines.append(f"- Query: {query}")
    lines.append(f"- Root: {root}")
    lines.append(f"- Regex: {str(regex).lower()}")
    lines.append(f"- Case sensitive: {str(case_sensitive).lower()}")
    lines.append(f"- Generated: {timestamp}")
    lines.append(f"- Matches: {total_matches} in {total_files} files")
    lines.append("")

    for path, matches in matches_by_file:
        if not matches:
            continue
        lines.append(f"## {path}")
        lines.append("")
        file_lines = load_lines(path)
        for line_no, _text in matches:
            lines.append(f"- L{line_no}")
            lines.append("```text")
            lines.append(render_context(file_lines, line_no, context))
            lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.path)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)
    exclude_exts = DEFAULT_EXCLUDE_EXTS | {ext.lower() for ext in args.exclude_ext}
    pattern = compile_pattern(args.query, args.regex, args.case_sensitive)
    max_size_bytes = args.max_size_kb * 1024

    matches_by_file: List[Tuple[str, List[Tuple[int, str]]]] = []
    total_matches = 0

    for path in iter_files(root, exclude_dirs, exclude_exts):
        matches = find_matches(path, pattern, max_size_bytes)
        if matches:
            matches_by_file.append((path, matches))
            total_matches += len(matches)
            if total_matches >= args.max_results:
                break

    report = build_report(
        query=args.query,
        root=root,
        regex=args.regex,
        case_sensitive=args.case_sensitive,
        context=max(0, args.context),
        matches_by_file=matches_by_file,
    )

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(report)
        except OSError as exc:
            sys.stderr.write(f"Failed to write {args.output}: {exc}\n")
            return 1
    else:
        sys.stdout.write(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
