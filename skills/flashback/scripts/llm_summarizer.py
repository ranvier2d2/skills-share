"""Condense and summarize Claude Code sessions.

Two paths:
1. **Heuristic** -- pure Python, no API calls, builds a summary dict
   from ParsedSession fields.
2. **LLM** -- pipes a condensed markdown document into
   ``claude -p --model haiku --output-format json`` for a richer narrative.

Both paths produce the same JSON schema so callers never need to branch.

No external dependencies beyond the Python 3.10+ standard library and the
sibling ``jsonl_parser`` module.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Sibling import: ensure the scripts directory is importable
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from jsonl_parser import ParsedSession, parse_session  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_PROMPT_CHARS = 300
_MAX_ERROR_CHARS = 200
_MAX_SNIPPET_CHARS = 200
_MAX_FILES_READ_DISPLAY = 10
_MAX_CONDENSED_CHARS = 16_000

_SYSTEM_PROMPT = (
    "You are a session summarizer for a coding project. "
    "Given a structured session summary, produce a JSON object with these "
    "exact keys:\n"
    '- "accomplishments": array of 3-5 bullet strings describing what was '
    "DONE (not planned)\n"
    '- "decisions": array of objects with "decision" and "rationale" string '
    "keys\n"
    '- "next_action": string describing the single most important next step\n'
    '- "open_questions": array of strings for unresolved issues (can be '
    "empty)\n"
    '- "session_one_liner": a single sentence summary of the session'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, limit: int) -> str:
    """Truncate *text* to *limit* characters, appending '...' if trimmed."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _date_part(iso_timestamp: str) -> str:
    """Extract the date portion (YYYY-MM-DD) from an ISO-8601 string."""
    if not iso_timestamp:
        return "unknown"
    return iso_timestamp[:10]


def _find_claude_binary() -> str | None:
    """Locate the ``claude`` CLI binary.

    Checks ``PATH`` first, then a common install location.
    Returns the absolute path or ``None`` if not found.
    """
    found = shutil.which("claude")
    if found is not None:
        return found
    fallback = Path("/usr/local/bin/claude")
    if fallback.is_file():
        return str(fallback)
    return None


# ---------------------------------------------------------------------------
# Function 1: build_condensed_context
# ---------------------------------------------------------------------------


def build_condensed_context(session: ParsedSession) -> str:
    """Build a markdown document from *session* data (~4k tokens).

    The output is designed to be piped into ``claude -p`` for LLM
    summarization.  Empty sections are omitted entirely.
    """
    m = session.metrics
    sections: list[str] = []

    # Header
    sections.append("# Session Summary Input\n")
    sections.append(f"Project: {session.project_path}")
    sections.append(f"Branch: {session.git_branch}")
    sections.append(f"Duration: {m.duration_minutes:.0f} minutes")
    sections.append(f"Date: {_date_part(session.start_time)}")
    sections.append(
        f"Messages: {m.message_count} | "
        f"Tool Calls: {m.tool_call_count} | "
        f"Errors: {m.error_count}"
    )

    # User prompts
    if session.user_prompts:
        lines: list[str] = ["\n## User's Prompts (chronological)"]
        for idx, prompt in enumerate(session.user_prompts, 1):
            lines.append(
                f'{idx}. "{_truncate(prompt, _MAX_PROMPT_CHARS)}"'
            )
        sections.append("\n".join(lines))

    # Files modified (edited + written)
    modified_lines: list[str] = []
    for fp in session.files_edited:
        modified_lines.append(f"- `{fp}` (edited)")
    for fp in session.files_written:
        modified_lines.append(f"- `{fp}` (created)")
    if modified_lines:
        sections.append(
            "\n## Files Modified\n" + "\n".join(modified_lines)
        )

    # Files read (capped)
    if session.files_read:
        lines = ["\n## Files Read (for context)"]
        display_count = min(len(session.files_read), _MAX_FILES_READ_DISPLAY)
        for fp in session.files_read[:display_count]:
            lines.append(f"- `{fp}`")
        remaining = len(session.files_read) - display_count
        if remaining > 0:
            lines.append(f"- ...and {remaining} more")
        sections.append("\n".join(lines))

    # Git operations
    if session.git_operations:
        lines = ["\n## Git Operations"]
        for op in session.git_operations:
            lines.append(f"- {op}")
        sections.append("\n".join(lines))

    # Errors
    if session.errors:
        lines = ["\n## Errors Encountered"]
        for err in session.errors:
            tool = err.get("tool", "unknown")
            error_text = _truncate(
                err.get("error", ""), _MAX_ERROR_CHARS
            )
            lines.append(f"- [{tool}] {error_text}")
        sections.append("\n".join(lines))

    # Subagent work
    if session.subagent_invocations:
        lines = ["\n## Subagent Work"]
        for sa in session.subagent_invocations:
            desc = sa.get("description", "")
            sa_type = sa.get("type", "")
            suffix = f" ({sa_type})" if sa_type else ""
            lines.append(f"- {desc}{suffix}")
        sections.append("\n".join(lines))

    # Decision snippets
    if session.decision_snippets:
        lines = ["\n## Decision Snippets"]
        for snippet in session.decision_snippets:
            lines.append(
                f'- "{_truncate(snippet, _MAX_SNIPPET_CHARS)}"'
            )
        sections.append("\n".join(lines))

    # TODO mentions
    if session.todo_mentions:
        lines = ["\n## TODO Mentions"]
        for todo in session.todo_mentions:
            lines.append(f"- {todo}")
        sections.append("\n".join(lines))

    result = "\n".join(sections)

    # Hard cap to stay within budget
    if len(result) > _MAX_CONDENSED_CHARS:
        result = result[:_MAX_CONDENSED_CHARS]

    return result


# ---------------------------------------------------------------------------
# Function 2: summarize_with_llm
# ---------------------------------------------------------------------------


def summarize_with_llm(
    condensed_context: str, project_name: str = ""
) -> dict[str, str | list[str] | list[dict[str, str]]] | None:
    """Summarize a session via ``claude -p``.

    Returns the parsed JSON dict on success, or ``None`` on any failure
    (missing binary, non-zero exit, unparseable output).
    """
    claude_bin = _find_claude_binary()
    if claude_bin is None:
        return None

    cmd: list[str] = [
        claude_bin,
        "-p",
        "--model",
        "haiku",
        "--output-format",
        "json",
        "--system-prompt",
        _SYSTEM_PROMPT,
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=condensed_context,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None

    if proc.returncode != 0:
        return None

    stdout = proc.stdout.strip()
    if not stdout:
        return None

    try:
        parsed: dict[str, str | list[str] | list[dict[str, str]]] = (
            json.loads(stdout)
        )
        return parsed
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Function 3: summarize_heuristic
# ---------------------------------------------------------------------------


def summarize_heuristic(
    session: ParsedSession,
) -> dict[str, str | list[str] | list[dict[str, str]]]:
    """Produce a summary dict using simple heuristics (no LLM call).

    Returns the same schema as the LLM summarizer so callers can treat
    both paths identically.
    """
    m = session.metrics

    # --- accomplishments ---
    accomplishments: list[str] = []

    total_modified = len(session.files_edited) + len(session.files_written)
    if total_modified > 0:
        accomplishments.append(
            f"Modified {total_modified} file(s) across the session"
        )

    git_commit_count = sum(
        1
        for op in session.git_operations
        if "commit" in op and "-m" in op
    )
    if git_commit_count > 0:
        accomplishments.append(f"Made {git_commit_count} git commit(s)")

    if m.error_count > 0:
        # Heuristic: if there are errors and tool calls continued after,
        # some errors were likely resolved.
        accomplishments.append(
            f"Encountered and worked through {m.error_count} error(s)"
        )

    subagent_count = len(session.subagent_invocations)
    if subagent_count > 0:
        accomplishments.append(
            f"Spawned {subagent_count} subagent(s) for parallel work"
        )

    if m.tool_call_count > 0 and not accomplishments:
        accomplishments.append(
            f"Executed {m.tool_call_count} tool call(s)"
        )

    # --- decisions ---
    decisions: list[dict[str, str]] = [
        {
            "decision": _truncate(snippet, _MAX_SNIPPET_CHARS),
            "rationale": "Detected from conversation",
        }
        for snippet in session.decision_snippets
    ]

    # --- next_action ---
    next_action: str
    if session.todo_mentions:
        next_action = session.todo_mentions[0]
    elif session.user_prompts:
        next_action = (
            "Continue from last user prompt: "
            + _truncate(session.user_prompts[-1], 120)
        )
    else:
        next_action = "Continue from last user prompt"

    # --- open_questions ---
    # Heuristic: errors near the end of the session might be unresolved.
    # "Near the end" = in the last quarter of errors by index.
    open_questions: list[str] = []
    if session.errors:
        cutoff = max(1, len(session.errors) * 3 // 4)
        tail_errors = session.errors[cutoff:]
        for err in tail_errors:
            tool = err.get("tool", "unknown")
            error_text = _truncate(err.get("error", ""), _MAX_ERROR_CHARS)
            open_questions.append(f"[{tool}] {error_text}")

    # --- session_one_liner ---
    branch_part = f" on branch {session.git_branch}" if session.git_branch else ""
    session_one_liner = (
        f"{total_modified} files modified, "
        f"{m.tool_call_count} tool calls "
        f"in {m.duration_minutes:.0f} minutes{branch_part}"
    )

    return {
        "accomplishments": accomplishments,
        "decisions": decisions,
        "next_action": next_action,
        "open_questions": open_questions,
        "session_one_liner": session_one_liner,
    }


# ---------------------------------------------------------------------------
# Function 4: generate_summary (main entry point)
# ---------------------------------------------------------------------------


def generate_summary(
    session: ParsedSession, use_llm: bool = True
) -> dict[str, str | list[str] | list[dict[str, str]]]:
    """Produce a session summary, optionally using the LLM.

    1. Build condensed context from the session.
    2. If *use_llm* is True, attempt LLM summarization.
    3. If the LLM call fails (or *use_llm* is False), fall back to
       the heuristic summarizer.
    4. The returned dict always includes a ``"source"`` key set to
       ``"llm"`` or ``"heuristic"``.
    """
    condensed = build_condensed_context(session)

    if use_llm:
        project_name = Path(session.project_path).name if session.project_path else ""
        result = summarize_with_llm(condensed, project_name=project_name)
        if result is not None:
            result["source"] = "llm"
            return result

    heuristic_result = summarize_heuristic(session)
    heuristic_result["source"] = "heuristic"
    return heuristic_result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI: ``python llm_summarizer.py <session.jsonl> [--no-llm]``."""
    if len(sys.argv) < 2:
        print(
            "Usage: python llm_summarizer.py <path-to-session.jsonl> "
            "[--no-llm]",
            file=sys.stderr,
        )
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    if not transcript_path.is_file():
        print(
            f"Error: File not found: {transcript_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    use_llm = "--no-llm" not in sys.argv

    session = parse_session(transcript_path)
    summary = generate_summary(session, use_llm=use_llm)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
