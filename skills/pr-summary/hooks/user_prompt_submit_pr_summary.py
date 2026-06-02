#!/usr/bin/env python3
"""Inject dynamic PR context when the prompt explicitly invokes $pr-summary."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SKILL_PATTERNS = (
    re.compile(r"(?<![\w-])\$pr-summary(?![\w-])"),
    re.compile(r"\[\$pr-summary\]\(", re.IGNORECASE),
    re.compile(r"skill://[^\s)]*pr-summary", re.IGNORECASE),
)


def prompt_invokes_skill(prompt: str) -> bool:
    return any(pattern.search(prompt) for pattern in SKILL_PATTERNS)


def hook_response(additional_context: str | None = None, system_message: str | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {}
    if system_message:
        response["systemMessage"] = system_message
    if additional_context:
        response["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    return response


def collector_path(plugin_root: Path) -> Path:
    override = os.environ.get("PR_SUMMARY_COLLECTOR_OVERRIDE")
    if override:
        return Path(override)
    return plugin_root / "skills" / "pr-summary" / "scripts" / "collect_pr_context.py"


def run_collector(plugin_root: Path, cwd: str) -> tuple[int, str, str]:
    collector = collector_path(plugin_root)
    command = [
        "python3",
        str(collector),
        "--format",
        "markdown",
        "--max-diff-chars",
        "24000",
        "--max-comments-chars",
        "12000",
        "--max-files",
        "200",
    ]
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=25,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def main() -> int:
    raw_stdin = sys.stdin.read()
    try:
        payload = json.loads(raw_stdin or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps(hook_response(system_message=f"pr-summary hook ignored invalid JSON: {exc}")))
        return 0

    prompt = str(payload.get("prompt") or "")
    if not prompt_invokes_skill(prompt):
        return 0

    plugin_root_raw = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root_raw:
        print(json.dumps(hook_response(system_message="pr-summary hook could not find PLUGIN_ROOT.")))
        return 0

    plugin_root = Path(plugin_root_raw)
    cwd = str(payload.get("cwd") or os.getcwd())
    try:
        returncode, stdout, stderr = run_collector(plugin_root, cwd)
    except subprocess.TimeoutExpired:
        print(json.dumps(hook_response(system_message="pr-summary hook timed out while collecting PR context.")))
        return 0
    except OSError as exc:
        print(json.dumps(hook_response(system_message=f"pr-summary hook failed to start collector: {exc}")))
        return 0

    if returncode != 0 and not stdout.strip():
        detail = stderr.strip() or f"collector exited with status {returncode}"
        context = (
            "## Dynamic PR context for $pr-summary\n\n"
            "The PR context collector did not return live data.\n\n"
            f"Collector diagnostic: {detail}"
        )
    else:
        diagnostic = f"\n\nCollector stderr:\n```text\n{stderr.strip()}\n```" if stderr.strip() else ""
        context = (
            "## Dynamic PR context for $pr-summary\n\n"
            "This context was collected by a Codex UserPromptSubmit hook before the pr-summary skill was injected.\n\n"
            f"{stdout.strip()}{diagnostic}"
        )

    print(json.dumps(hook_response(additional_context=context)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
