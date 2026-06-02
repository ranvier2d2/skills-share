#!/usr/bin/env python3
"""Out-of-band Flashback analyzer.

Reads Claude Code session JSONL transcripts, extracts structured data via
heuristics, optionally generates a narrative summary via ``claude -p``, and
produces two artifacts:

1. Restart prompt markdown  (``output/flashback/flashback_YYYY-MM-DD_HHMM.md``)
2. Session digest JSON      (``output/flashback/digest_YYYY-MM-DD_HHMM.json``)

Can be invoked manually or triggered by a ``SessionEnd`` hook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure sibling modules are importable
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from flashback_core import (
    _stamp_now,
    detect_decisions,
    extract_pending_todos,
    find_task_files,
    parse_active_tasks,
    summarize_git_state,
)
from jsonl_parser import ParsedSession, find_latest_session, parse_session
from llm_summarizer import build_condensed_context, generate_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_memory(repo_root: Path) -> tuple[Path | None, str]:
    """Discover and read the project's MEMORY.md file."""
    candidates = [
        repo_root / "MEMORY.md",
        repo_root / "memory" / "MEMORY.md",
        repo_root / "ai_docs" / "MEMORY.md",
    ]

    # Also check Claude project memory
    home = Path.home()
    encoded = str(repo_root).replace("/", "-")
    claude_memory = home / ".claude" / "projects" / encoded / "memory" / "MEMORY.md"
    candidates.append(claude_memory)

    for path in candidates:
        if path.exists():
            return path, path.read_text(encoding="utf-8", errors="ignore")

    return None, ""


def _build_restart_prompt(
    session: ParsedSession,
    summary: dict,
    active_tasks: list[dict[str, str]],
    pending_todos: list[str],
    task_files: list[Path],
    memory_path: Path | None,
    git_warnings: list[str],
) -> str:
    """Build the restart prompt markdown from session data + summary."""
    project_name = Path(session.project_path).name or "Unknown Project"
    lines: list[str] = []

    lines.append(f"I'm continuing work on {project_name}.")
    lines.append("")
    lines.append("Read your memory files to orient, then here's the session context:")
    lines.append("")

    # Accomplishments
    lines.append("## What Was Accomplished Last Session")
    accomplishments = summary.get("accomplishments", [])
    if accomplishments:
        for bullet in accomplishments[:5]:
            lines.append(f"- {bullet}")
    else:
        lines.append("- Session data extracted but no accomplishments summarized.")

    # Decisions
    decisions = summary.get("decisions", [])
    if decisions:
        lines.append("")
        lines.append("## Locked Decisions (Do Not Re-Litigate)")
        lines.append("| Decision | Rationale | Date |")
        lines.append("|----------|-----------|------|")
        today = datetime.now().strftime("%Y-%m-%d")
        for d in decisions[:10]:
            dec = d.get("decision", "").replace("|", "/")
            rat = d.get("rationale", "").replace("|", "/")
            lines.append(f"| {dec} | {rat} | {today} |")

    # Active tasks
    lines.append("")
    lines.append("## Active Tasks")
    if active_tasks:
        lines.append("| Task | Status | Next Action |")
        lines.append("|------|--------|-------------|")
        for task in active_tasks:
            t = task.get("task", "").replace("|", "/")
            s = task.get("status", "").replace("|", "/")
            n = task.get("next_action", "").replace("|", "/")
            lines.append(f"| {t} | {s} | {n} |")
    else:
        lines.append("No active tasks found in memory.")

    # Immediate next action
    lines.append("")
    lines.append("## Immediate Next Action")
    next_action = summary.get("next_action", "")
    if next_action:
        lines.append(next_action)
    elif pending_todos:
        lines.append(f"Address highest-priority pending TODO: {pending_todos[0]}")
    else:
        lines.append("Read MEMORY.md and continue the highest-priority active task.")

    # Pending TODOs
    lines.append("")
    lines.append("## Pending TODOs")
    if pending_todos:
        for todo in pending_todos[:15]:
            lines.append(f"- {todo}")
    else:
        lines.append("- No pending TODOs detected from active task files.")

    # Files modified this session
    files_modified = sorted(set(session.files_edited + session.files_written))
    if files_modified:
        lines.append("")
        lines.append("## Files Modified Last Session")
        for fp in files_modified:
            if fp in session.files_written and fp not in session.files_edited:
                lines.append(f"- `{fp}` (created)")
            else:
                lines.append(f"- `{fp}` (edited)")

    # Files to read
    lines.append("")
    lines.append("## Files to Read First (in order)")
    read_order: list[tuple[str, str]] = []
    if memory_path:
        read_order.append((str(memory_path), "Primary project memory state"))
    for tf in task_files:
        read_order.append((str(tf), "Active task context and TODOs"))
    # Add files modified this session (they provide recent context)
    for fp in files_modified[:3]:
        read_order.append((fp, "Modified last session"))
    for idx, (path, why) in enumerate(read_order[:8], start=1):
        lines.append(f"{idx}. `{path}` — {why}")

    # Session continuity
    lines.append("")
    lines.append("## Session Continuity")
    lines.append(f"- Previous session: `{session.session_id}` (resume with `claude --resume {session.session_id}`)")
    lines.append(f"- Branch: {session.git_branch}")
    m = session.metrics
    tokens_k = (m.total_input_tokens + m.total_output_tokens) / 1000
    lines.append(f"- Duration: {m.duration_minutes:.0f} min | Messages: {m.message_count} | Tokens: {tokens_k:.0f}k")

    # Open questions
    open_questions = summary.get("open_questions", [])
    if open_questions:
        lines.append("")
        lines.append("## Open Questions")
        for q in open_questions[:5]:
            lines.append(f"- {q}")

    # Warnings
    lines.append("")
    lines.append("## Warnings")
    if git_warnings:
        for w in git_warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- No blocking warnings detected.")

    lines.append("")
    lines.append("Don't start executing yet — read the referenced files first, then confirm your understanding before proceeding.")

    return "\n".join(lines) + "\n"


def _build_digest(
    session: ParsedSession,
    summary: dict,
    active_tasks: list[dict[str, str]],
    pending_todos: list[str],
) -> dict:
    """Build the session digest JSON object."""
    m = session.metrics
    return {
        "session_id": session.session_id,
        "project": session.project_path,
        "branch": session.git_branch,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "duration_minutes": round(m.duration_minutes, 1),
        "metrics": {
            "message_count": m.message_count,
            "total_input_tokens": m.total_input_tokens,
            "total_output_tokens": m.total_output_tokens,
            "tool_calls": m.tool_call_count,
            "errors": m.error_count,
            "compactions": m.compaction_count,
            "estimated_cost_usd": round(m.estimated_cost_usd, 4),
        },
        "files": {
            "read": session.files_read,
            "edited": session.files_edited,
            "written": session.files_written,
        },
        "git_operations": session.git_operations,
        "active_tasks": active_tasks,
        "pending_todos": pending_todos[:20],
        "accomplishments": summary.get("accomplishments", []),
        "decisions": summary.get("decisions", []),
        "next_action": summary.get("next_action", ""),
        "open_questions": summary.get("open_questions", []),
        "summary_source": summary.get("source", "unknown"),
        "session_one_liner": summary.get("session_one_liner", ""),
    }


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_analyzer(
    transcript_path: Path,
    repo_root: Path,
    use_llm: bool = True,
    dry_run: bool = False,
) -> tuple[Path | None, Path | None, dict]:
    """Run the full out-of-band analysis pipeline.

    Returns (prompt_path, digest_path, digest_dict).
    """
    # 1. Parse JSONL transcript
    session = parse_session(transcript_path)

    # 2. Read memory + extract tasks
    memory_path, memory_text = _read_memory(repo_root)
    active_tasks = parse_active_tasks(memory_text)
    task_files = find_task_files(repo_root, active_tasks)

    # Fallback: if no active tasks, discover recent task files
    if not active_tasks and not task_files:
        task_dir = repo_root / "ai_docs" / "tasks"
        if task_dir.exists():
            all_task_files = sorted(
                task_dir.glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            task_files = all_task_files[:3]

    pending_todos, _ = extract_pending_todos(task_files)

    # 3. Generate summary (hybrid: heuristics + optional LLM)
    summary = generate_summary(session, use_llm=use_llm)

    # 4. Git state
    git_warnings, _ = summarize_git_state(repo_root)

    # 5. Build artifacts
    prompt_text = _build_restart_prompt(
        session=session,
        summary=summary,
        active_tasks=active_tasks,
        pending_todos=pending_todos,
        task_files=task_files,
        memory_path=memory_path,
        git_warnings=git_warnings,
    )
    digest = _build_digest(session, summary, active_tasks, pending_todos)

    if dry_run:
        print("=== RESTART PROMPT (dry-run) ===")
        print(prompt_text)
        print("=== DIGEST (dry-run) ===")
        print(json.dumps(digest, indent=2))
        return None, None, digest

    # 6. Write artifacts
    out_dir = repo_root / "output" / "flashback"
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = _stamp_now()
    prompt_path = out_dir / f"flashback_{stamp}.md"
    digest_path = out_dir / f"digest_{stamp}.json"

    prompt_path.write_text(prompt_text, encoding="utf-8")
    digest_path.write_text(
        json.dumps(digest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    # 7. Copy to clipboard (macOS)
    try:
        subprocess.run(
            ["pbcopy"],
            input=prompt_text.encode("utf-8"),
            check=True,
            timeout=5,
        )
        clipboard_status = "copied"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        clipboard_status = "skipped"

    # 8. Print summary
    m = session.metrics
    print("FLASHBACK ANALYZER COMPLETE")
    print(f"  Session:       {session.session_id}")
    print(f"  Branch:        {session.git_branch}")
    print(f"  Duration:      {m.duration_minutes:.0f} min")
    print(f"  Messages:      {m.message_count}")
    print(f"  Tool Calls:    {m.tool_call_count}")
    print(f"  Files Modified:{len(session.files_edited) + len(session.files_written)}")
    print(f"  Summary:       {summary.get('source', 'unknown')}")
    print(f"  Restart prompt:{prompt_path}")
    print(f"  Session digest:{digest_path}")
    print(f"  Clipboard:     {clipboard_status}")

    return prompt_path, digest_path, digest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Out-of-band Flashback analyzer: parse session JSONL → restart prompt + digest.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--transcript",
        type=str,
        help="Path to session JSONL transcript file",
    )
    group.add_argument(
        "--latest",
        action="store_true",
        help="Auto-discover the latest session JSONL for the project",
    )
    group.add_argument(
        "--session-id",
        type=str,
        help="Session ID (UUID) — will search the project's JSONL directory",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM summarization, use heuristics only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print artifacts to stdout without writing files",
    )
    return parser.parse_args()


def _find_session_by_id(repo_root: Path, session_id: str) -> Path | None:
    """Find a session JSONL file by session ID."""
    home = Path.home()
    encoded = str(repo_root).replace("/", "-")
    project_dir = home / ".claude" / "projects" / encoded

    if not project_dir.exists():
        return None

    # Try exact filename match
    exact = project_dir / f"{session_id}.jsonl"
    if exact.exists():
        return exact

    # Try prefix match
    for f in project_dir.glob("*.jsonl"):
        if f.stem.startswith(session_id) and not f.stem.startswith("agent-"):
            return f

    return None


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()

    # Resolve transcript path
    if args.transcript:
        transcript_path = Path(args.transcript).expanduser().resolve()
    elif args.latest:
        transcript_path = find_latest_session(repo_root)
        if transcript_path is None:
            print("ERROR: No session JSONL files found for this project.", file=sys.stderr)
            return 2
        print(f"Using latest session: {transcript_path.name}")
    elif args.session_id:
        transcript_path = _find_session_by_id(repo_root, args.session_id)
        if transcript_path is None:
            print(f"ERROR: No session found for ID: {args.session_id}", file=sys.stderr)
            return 2
        print(f"Found session: {transcript_path.name}")
    else:
        print("ERROR: Must specify --transcript, --latest, or --session-id", file=sys.stderr)
        return 2

    if not transcript_path.is_file():
        print(f"ERROR: Transcript not found: {transcript_path}", file=sys.stderr)
        return 2

    run_analyzer(
        transcript_path=transcript_path,
        repo_root=repo_root,
        use_llm=not args.no_llm,
        dry_run=args.dry_run,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
