#!/usr/bin/env python3
"""Collect current GitHub PR context for a Codex skill."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


DEFAULT_JSON_FIELDS = (
    "number,url,title,state,isDraft,author,baseRefName,headRefName,"
    "reviewDecision,mergeable,additions,deletions,changedFiles,statusCheckRollup"
)


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    command: list[str]


def run(command: list[str], timeout: int = 20) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(False, "", str(exc), command)
    return CommandResult(completed.returncode == 0, completed.stdout, completed.stderr, command)


def truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars].rstrip() + f"\n\n[truncated {omitted} characters]"


def compact_status_checks(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    checks: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("context") or item.get("workflowName") or "check"
        status = item.get("status") or item.get("conclusion") or item.get("state") or "unknown"
        checks.append(f"{name}: {status}")
    return checks[:20]


def format_metadata(data: dict[str, Any]) -> str:
    author = data.get("author")
    if isinstance(author, dict):
        author = author.get("login") or author.get("name")
    lines = [
        f"- PR: #{data.get('number', 'unknown')} {data.get('title', '')}".rstrip(),
        f"- URL: {data.get('url', 'unknown')}",
        f"- State: {data.get('state', 'unknown')}",
        f"- Draft: {data.get('isDraft', 'unknown')}",
        f"- Author: {author or 'unknown'}",
        f"- Base: {data.get('baseRefName', 'unknown')}",
        f"- Head: {data.get('headRefName', 'unknown')}",
        f"- Review decision: {data.get('reviewDecision', 'unknown')}",
        f"- Mergeable: {data.get('mergeable', 'unknown')}",
        f"- Size: +{data.get('additions', 'unknown')} -{data.get('deletions', 'unknown')} across {data.get('changedFiles', 'unknown')} files",
    ]
    checks = compact_status_checks(data.get("statusCheckRollup"))
    if checks:
        lines.append("- Status checks:")
        lines.extend(f"  - {check}" for check in checks)
    return "\n".join(lines)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    if not shutil.which("gh"):
        return {"ok": False, "error": "GitHub CLI `gh` was not found on PATH."}

    metadata = run(["gh", "pr", "view", "--json", DEFAULT_JSON_FIELDS])
    files = run(["gh", "pr", "diff", "--name-only"])
    comments = run(["gh", "pr", "view", "--comments"])
    diff = run(["gh", "pr", "diff"])

    result: dict[str, Any] = {
        "ok": metadata.ok,
        "commands": {
            "metadata": metadata.command,
            "files": files.command,
            "comments": comments.command,
            "diff": diff.command,
        },
        "errors": {},
    }
    if metadata.ok:
        try:
            result["metadata"] = json.loads(metadata.stdout or "{}")
        except json.JSONDecodeError as exc:
            result["ok"] = False
            result["errors"]["metadata"] = f"invalid JSON: {exc}"
    else:
        result["errors"]["metadata"] = metadata.stderr.strip()

    changed_files = [line for line in files.stdout.splitlines() if line.strip()]
    result["changed_files"] = changed_files[: args.max_files]
    if len(changed_files) > args.max_files:
        result["changed_files_truncated"] = len(changed_files) - args.max_files
    if not files.ok:
        result["errors"]["files"] = files.stderr.strip()

    result["comments"] = truncate(comments.stdout.strip(), args.max_comments_chars)
    if not comments.ok:
        result["errors"]["comments"] = comments.stderr.strip()

    result["diff"] = truncate(diff.stdout.strip(), args.max_diff_chars)
    if not diff.ok:
        result["errors"]["diff"] = diff.stderr.strip()

    return result


def to_markdown(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        errors = data.get("errors") or {}
        detail = errors.get("metadata") or data.get("error") or "unknown error"
        return f"### PR metadata unavailable\n\n{detail}\n"

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    files = data.get("changed_files") if isinstance(data.get("changed_files"), list) else []
    comments = str(data.get("comments") or "")
    diff = str(data.get("diff") or "")
    sections = [
        "### PR metadata",
        format_metadata(metadata),
        "",
        "### Changed files",
    ]
    if files:
        sections.extend(f"- {path}" for path in files)
        if data.get("changed_files_truncated"):
            sections.append(f"- [truncated {data['changed_files_truncated']} additional files]")
    else:
        sections.append("No changed files reported.")
    sections.extend(["", "### PR comments", comments or "No comments reported."])
    sections.extend(["", "### PR diff", "```diff", diff or "No diff reported.", "```"])

    errors = data.get("errors") if isinstance(data.get("errors"), dict) else {}
    if errors:
        sections.extend(["", "### Collector diagnostics"])
        sections.extend(f"- {key}: {value}" for key, value in errors.items() if value)
    return "\n".join(sections).strip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--max-diff-chars", type=int, default=24000)
    parser.add_argument("--max-comments-chars", type=int, default=12000)
    parser.add_argument("--max-files", type=int, default=200)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    data = collect(args)
    if args.format == "markdown":
        sys.stdout.write(to_markdown(data))
    else:
        json.dump(data, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
