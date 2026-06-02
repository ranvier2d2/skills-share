"""Parse Claude Code session JSONL transcripts into structured data.

This module reads raw JSONL transcript files produced by Claude Code,
extracts tool calls, token usage, file operations, bash commands,
decision points, and other structured data for the flashback skill's
out-of-band analyzer.

No external dependencies beyond the Python 3.10+ standard library.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Decision-keyword pattern (case-insensitive, whole-word where practical)
# ---------------------------------------------------------------------------
_DECISION_KEYWORDS: list[str] = [
    "LOCKED",
    "DECIDED",
    "FROZEN",
    "RESOLVED",
    "let's go with",
    "we decided",
    "use .+ instead",
    "approved",
]
_DECISION_RE = re.compile(
    "|".join(_DECISION_KEYWORDS),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bash-command category prefixes
# ---------------------------------------------------------------------------
_BASH_CATEGORIES: list[tuple[list[str], str]] = [
    (["git "], "git"),
    (
        [
            "pytest",
            "vitest",
            "pnpm test",
            "pnpm run test",
            "npm test",
            "npm run test",
            "uv run pytest",
            "uv run --group test pytest",
        ],
        "test",
    ),
    (
        [
            "pnpm build",
            "pnpm run build",
            "npm run build",
            "next build",
        ],
        "build",
    ),
    (
        [
            "pnpm add",
            "pnpm install",
            "pip install",
            "uv add",
            "uv sync",
            "npm install",
            "npm i ",
        ],
        "install",
    ),
    (
        [
            "ruff",
            "mypy",
            "eslint",
            "pnpm lint",
            "pnpm run lint",
            "npm run lint",
            "black",
            "prettier",
        ],
        "lint",
    ),
]

# ---------------------------------------------------------------------------
# Rough per-token pricing (USD) — Claude Sonnet ballpark
# ---------------------------------------------------------------------------
_INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000
_CACHE_READ_COST_PER_TOKEN = 0.3 / 1_000_000
_CACHE_CREATION_COST_PER_TOKEN = 3.75 / 1_000_000

# Tool names we care about for file-operation tracking
_FILE_READ_TOOLS = {"Read"}
_FILE_EDIT_TOOLS = {"Edit"}
_FILE_WRITE_TOOLS = {"Write"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ToolCall:
    """A single tool invocation extracted from the transcript."""

    tool_name: str
    input_args: dict[str, str | int | float | bool | None]
    timestamp: str
    is_error: bool = False
    error_text: str = ""


@dataclass
class SessionMetrics:
    """Aggregate numeric metrics for a session."""

    message_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    tool_call_count: int = 0
    error_count: int = 0
    compaction_count: int = 0
    duration_minutes: float = 0.0
    estimated_cost_usd: float = 0.0


@dataclass
class ParsedSession:
    """Fully parsed representation of a Claude Code session."""

    session_id: str = ""
    project_path: str = ""
    git_branch: str = ""
    start_time: str = ""
    end_time: str = ""
    metrics: SessionMetrics = field(default_factory=SessionMetrics)

    user_prompts: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    bash_commands: list[dict[str, str]] = field(default_factory=list)
    git_operations: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    subagent_invocations: list[dict[str, str]] = field(default_factory=list)
    decision_snippets: list[str] = field(default_factory=list)
    todo_mentions: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def categorize_bash_command(command: str) -> str:
    """Categorize a bash command into: git, test, build, install, lint, other."""
    stripped = command.strip()
    for prefixes, category in _BASH_CATEGORIES:
        for prefix in prefixes:
            if stripped.startswith(prefix):
                return category
    return "other"


def _parse_timestamp(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime."""
    if not raw:
        return None
    try:
        # Handle trailing 'Z' (common in JS-originated timestamps)
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def _extract_text_from_content(
    content: str | list[dict[str, str | dict[str, str | int | float | bool | None]]],
) -> str:
    """Return concatenated text from a message content field.

    ``content`` may be a plain string or a list of content blocks.
    Only blocks with ``type == "text"`` contribute text.
    """
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_value = block.get("text", "")
            if isinstance(text_value, str):
                parts.append(text_value)
    return "\n".join(parts)


def _extract_tool_uses(
    content: str | list[dict[str, str | dict[str, str | int | float | bool | None]]],
) -> list[dict[str, str | dict[str, str | int | float | bool | None]]]:
    """Return a list of tool_use blocks from a message content field."""
    if isinstance(content, str):
        return []
    results: list[dict[str, str | dict[str, str | int | float | bool | None]]] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            results.append(block)
    return results


def _extract_tool_results(
    content: str | list[dict[str, str | dict[str, str | int | float | bool | None]]],
) -> list[dict[str, str | bool]]:
    """Return a list of tool_result blocks from a message content field."""
    if isinstance(content, str):
        return []
    results: list[dict[str, str | bool]] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            results.append(block)  # type narrowing handled by caller
    return results


def _estimate_cost(metrics: SessionMetrics) -> float:
    """Compute a rough USD cost estimate from token counts."""
    return (
        metrics.total_input_tokens * _INPUT_COST_PER_TOKEN
        + metrics.total_output_tokens * _OUTPUT_COST_PER_TOKEN
        + metrics.total_cache_read_tokens * _CACHE_READ_COST_PER_TOKEN
        + metrics.total_cache_creation_tokens * _CACHE_CREATION_COST_PER_TOKEN
    )


def _scan_decisions(text: str) -> list[str]:
    """Return individual lines from *text* that match decision keywords."""
    hits: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and _DECISION_RE.search(stripped):
            hits.append(stripped)
    return hits


def _scan_todos(text: str) -> list[str]:
    """Return lines containing TODO or FIXME markers."""
    results: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and re.search(r"\b(TODO|FIXME)\b", stripped, re.IGNORECASE):
            results.append(stripped)
    return results


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


def parse_session(transcript_path: str | Path) -> ParsedSession:
    """Parse a Claude Code session JSONL file into structured data.

    Each line in the file is expected to be a JSON object representing one
    message in the conversation.  Malformed lines are silently skipped.

    Args:
        transcript_path: Path to the ``.jsonl`` transcript file.

    Returns:
        A fully populated ``ParsedSession`` instance.
    """
    path = Path(transcript_path)
    session = ParsedSession()
    metrics = SessionMetrics()

    # Internal sets for deduplication
    files_read_set: set[str] = set()
    files_edited_set: set[str] = set()
    files_written_set: set[str] = set()

    # Map tool_use_id -> ToolCall for error pairing
    pending_tool_calls: dict[str, ToolCall] = {}

    first_ts: datetime | None = None
    last_ts: datetime | None = None

    with path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                entry: dict[str, str | bool | dict[str, str | int | float | bool | None | list[dict[str, str | dict[str, str | int | float | bool | None]]]]] = json.loads(raw_line)
            except (json.JSONDecodeError, ValueError):
                continue

            # Skip sidechain (subagent) messages for main analysis,
            # but note them as subagent activity.
            if entry.get("isSidechain") is True:
                continue

            # Skip meta messages
            if entry.get("isMeta") is True:
                # Detect compaction events (system summarization)
                message = entry.get("message")
                if isinstance(message, dict):
                    content = message.get("content", "")
                    text = _extract_text_from_content(content)
                    if "compaction" in text.lower() or "summariz" in text.lower():
                        metrics.compaction_count += 1
                continue

            metrics.message_count += 1

            # Extract top-level metadata (take first non-empty values)
            if not session.session_id:
                sid = entry.get("sessionId")
                if isinstance(sid, str) and sid:
                    session.session_id = sid

            if not session.project_path:
                cwd = entry.get("cwd")
                if isinstance(cwd, str) and cwd:
                    session.project_path = cwd

            if not session.git_branch:
                branch = entry.get("gitBranch")
                if isinstance(branch, str) and branch:
                    session.git_branch = branch

            # Timestamp tracking
            ts_raw = entry.get("timestamp")
            ts_str = ts_raw if isinstance(ts_raw, str) else ""
            ts_dt = _parse_timestamp(ts_str)
            if ts_dt is not None:
                if first_ts is None or ts_dt < first_ts:
                    first_ts = ts_dt
                if last_ts is None or ts_dt > last_ts:
                    last_ts = ts_dt

            msg_type = entry.get("type", "")
            user_type = entry.get("userType", "")
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content", "")

            # ----------------------------------------------------------
            # Human user messages
            # ----------------------------------------------------------
            if msg_type == "user" and user_type == "human":
                text = _extract_text_from_content(content)
                if text.strip():
                    session.user_prompts.append(text.strip())
                continue

            # ----------------------------------------------------------
            # Tool results (external user type)
            # ----------------------------------------------------------
            if msg_type == "user" and user_type == "external":
                tool_results = _extract_tool_results(content)
                for tr in tool_results:
                    tool_use_id = tr.get("tool_use_id", "")
                    is_error = tr.get("is_error", False) is True
                    if is_error and isinstance(tool_use_id, str):
                        result_content = tr.get("content", "")
                        error_text = ""
                        if isinstance(result_content, str):
                            error_text = result_content
                        elif isinstance(result_content, list):
                            error_text = _extract_text_from_content(result_content)
                        metrics.error_count += 1

                        # Pair with pending tool call
                        if tool_use_id in pending_tool_calls:
                            tc = pending_tool_calls[tool_use_id]
                            tc.is_error = True
                            tc.error_text = error_text
                            session.errors.append(
                                {
                                    "tool": tc.tool_name,
                                    "error": error_text[:500],
                                    "timestamp": tc.timestamp,
                                }
                            )
                continue

            # ----------------------------------------------------------
            # Assistant messages
            # ----------------------------------------------------------
            if msg_type == "assistant":
                # Accumulate token usage
                usage = entry.get("usage")
                if isinstance(usage, dict):
                    input_t = usage.get("input_tokens", 0)
                    output_t = usage.get("output_tokens", 0)
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    cache_create = usage.get("cache_creation_input_tokens", 0)
                    metrics.total_input_tokens += int(input_t) if isinstance(input_t, (int, float)) else 0
                    metrics.total_output_tokens += int(output_t) if isinstance(output_t, (int, float)) else 0
                    metrics.total_cache_read_tokens += int(cache_read) if isinstance(cache_read, (int, float)) else 0
                    metrics.total_cache_creation_tokens += int(cache_create) if isinstance(cache_create, (int, float)) else 0

                # Extract assistant text for decision/todo scanning
                text = _extract_text_from_content(content)
                if text:
                    session.decision_snippets.extend(_scan_decisions(text))
                    session.todo_mentions.extend(_scan_todos(text))

                # Extract tool use blocks
                tool_uses = _extract_tool_uses(content)
                for tu in tool_uses:
                    tool_name_raw = tu.get("name", "")
                    tool_name = tool_name_raw if isinstance(tool_name_raw, str) else str(tool_name_raw)
                    tool_input_raw = tu.get("input", {})
                    tool_input: dict[str, str | int | float | bool | None] = (
                        tool_input_raw if isinstance(tool_input_raw, dict) else {}
                    )
                    tool_id_raw = tu.get("id", "")
                    tool_id = tool_id_raw if isinstance(tool_id_raw, str) else str(tool_id_raw)

                    metrics.tool_call_count += 1

                    tc = ToolCall(
                        tool_name=tool_name,
                        input_args=dict(tool_input),
                        timestamp=ts_str,
                    )
                    session.tool_calls.append(tc)
                    pending_tool_calls[tool_id] = tc

                    # ---- File operations ----
                    if tool_name in _FILE_READ_TOOLS:
                        fp = tool_input.get("file_path", "")
                        if isinstance(fp, str) and fp:
                            files_read_set.add(fp)

                    elif tool_name in _FILE_EDIT_TOOLS:
                        fp = tool_input.get("file_path", "")
                        if isinstance(fp, str) and fp:
                            files_edited_set.add(fp)

                    elif tool_name in _FILE_WRITE_TOOLS:
                        fp = tool_input.get("file_path", "")
                        if isinstance(fp, str) and fp:
                            files_written_set.add(fp)

                    # ---- Bash commands ----
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        desc = tool_input.get("description", "")
                        cmd_str = cmd if isinstance(cmd, str) else str(cmd)
                        desc_str = desc if isinstance(desc, str) else str(desc)
                        category = categorize_bash_command(cmd_str)
                        entry_dict: dict[str, str] = {
                            "command": cmd_str,
                            "description": desc_str,
                            "category": category,
                        }
                        session.bash_commands.append(entry_dict)
                        if category == "git":
                            session.git_operations.append(cmd_str)

                    # ---- Subagent invocations ----
                    elif tool_name in {"Task", "TaskCreate"}:
                        description = tool_input.get("description", "")
                        subject = tool_input.get("subject", "")
                        prompt = tool_input.get("prompt", "")
                        subagent_type = tool_input.get("subagent_type", "")

                        desc_text = ""
                        if isinstance(description, str) and description:
                            desc_text = description
                        elif isinstance(subject, str) and subject:
                            desc_text = subject
                        elif isinstance(prompt, str) and prompt:
                            desc_text = prompt

                        type_text = (
                            subagent_type
                            if isinstance(subagent_type, str)
                            else str(subagent_type)
                        )

                        session.subagent_invocations.append(
                            {
                                "description": desc_text,
                                "type": type_text,
                                "timestamp": ts_str,
                            }
                        )

                        # TaskCreate subjects count as TODO mentions
                        if tool_name == "TaskCreate" and isinstance(subject, str) and subject:
                            session.todo_mentions.append(f"TaskCreate: {subject}")

                    # ---- Task status updates ----
                    elif tool_name == "TaskUpdate":
                        task_id = tool_input.get("taskId", "")
                        status = tool_input.get("status", "")
                        session.subagent_invocations.append(
                            {
                                "description": f"TaskUpdate {task_id} -> {status}",
                                "type": "status_update",
                                "timestamp": ts_str,
                            }
                        )

                continue

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------
    session.files_read = sorted(files_read_set)
    session.files_edited = sorted(files_edited_set)
    session.files_written = sorted(files_written_set)

    # Timestamps
    if first_ts is not None:
        session.start_time = first_ts.isoformat()
    if last_ts is not None:
        session.end_time = last_ts.isoformat()

    # Duration
    if first_ts is not None and last_ts is not None:
        delta = last_ts - first_ts
        metrics.duration_minutes = round(delta.total_seconds() / 60.0, 2)

    # Cost estimate
    metrics.estimated_cost_usd = round(_estimate_cost(metrics), 4)

    session.metrics = metrics
    return session


# ---------------------------------------------------------------------------
# Session file discovery
# ---------------------------------------------------------------------------


def find_latest_session(project_path: str | Path) -> Path | None:
    """Find the most recently modified .jsonl session file for a project.

    Looks in ``~/.claude/projects/{encoded_path}/`` for ``.jsonl`` files.
    The encoding rule replaces ``/`` with ``-`` in the absolute project path.
    Sub-agent transcripts (``agent-*.jsonl``) are excluded.

    Args:
        project_path: Absolute path to the project directory.

    Returns:
        Path to the most recently modified session file, or ``None``.
    """
    project_str = str(Path(project_path).resolve())

    # Encode path: strip leading slash, replace remaining slashes with '-'
    encoded = project_str.lstrip("/").replace("/", "-")

    sessions_dir = Path.home() / ".claude" / "projects" / encoded

    if not sessions_dir.is_dir():
        return None

    candidates: list[Path] = []
    for jsonl_file in sessions_dir.glob("*.jsonl"):
        # Exclude subagent transcript files
        if jsonl_file.name.startswith("agent-"):
            continue
        candidates.append(jsonl_file)

    if not candidates:
        return None

    # Return the most recently modified file
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _format_summary(session: ParsedSession) -> str:
    """Format a parsed session into a human-readable summary."""
    m = session.metrics
    lines: list[str] = [
        "=" * 72,
        "CLAUDE CODE SESSION SUMMARY",
        "=" * 72,
        "",
        f"Session ID:    {session.session_id}",
        f"Project:       {session.project_path}",
        f"Git Branch:    {session.git_branch}",
        f"Start:         {session.start_time}",
        f"End:           {session.end_time}",
        f"Duration:      {m.duration_minutes:.1f} minutes",
        "",
        "--- Metrics ---",
        f"Messages:           {m.message_count}",
        f"Tool Calls:         {m.tool_call_count}",
        f"Errors:             {m.error_count}",
        f"Compactions:        {m.compaction_count}",
        f"Input Tokens:       {m.total_input_tokens:,}",
        f"Output Tokens:      {m.total_output_tokens:,}",
        f"Cache Read Tokens:  {m.total_cache_read_tokens:,}",
        f"Cache Create Tokens:{m.total_cache_creation_tokens:,}",
        f"Est. Cost (USD):    ${m.estimated_cost_usd:.4f}",
        "",
    ]

    if session.user_prompts:
        lines.append(f"--- User Prompts ({len(session.user_prompts)}) ---")
        for i, prompt in enumerate(session.user_prompts, 1):
            # Truncate long prompts for display
            display = prompt[:200] + "..." if len(prompt) > 200 else prompt
            lines.append(f"  {i}. {display}")
        lines.append("")

    if session.files_read:
        lines.append(f"--- Files Read ({len(session.files_read)}) ---")
        for fp in session.files_read:
            lines.append(f"  - {fp}")
        lines.append("")

    if session.files_edited:
        lines.append(f"--- Files Edited ({len(session.files_edited)}) ---")
        for fp in session.files_edited:
            lines.append(f"  - {fp}")
        lines.append("")

    if session.files_written:
        lines.append(f"--- Files Written ({len(session.files_written)}) ---")
        for fp in session.files_written:
            lines.append(f"  - {fp}")
        lines.append("")

    if session.bash_commands:
        lines.append(f"--- Bash Commands ({len(session.bash_commands)}) ---")
        for cmd in session.bash_commands:
            label = f"[{cmd['category']}]"
            desc = f" ({cmd['description']})" if cmd.get("description") else ""
            lines.append(f"  {label:10s} {cmd['command'][:120]}{desc}")
        lines.append("")

    if session.git_operations:
        lines.append(f"--- Git Operations ({len(session.git_operations)}) ---")
        for op in session.git_operations:
            lines.append(f"  - {op[:120]}")
        lines.append("")

    if session.errors:
        lines.append(f"--- Errors ({len(session.errors)}) ---")
        for err in session.errors:
            lines.append(f"  [{err.get('tool', '?')}] {err.get('error', '')[:200]}")
        lines.append("")

    if session.subagent_invocations:
        lines.append(
            f"--- Subagent Invocations ({len(session.subagent_invocations)}) ---"
        )
        for sa in session.subagent_invocations:
            lines.append(f"  - {sa.get('description', '')[:150]}")
        lines.append("")

    if session.decision_snippets:
        lines.append(f"--- Decision Snippets ({len(session.decision_snippets)}) ---")
        for snippet in session.decision_snippets:
            lines.append(f"  > {snippet[:200]}")
        lines.append("")

    if session.todo_mentions:
        lines.append(f"--- TODO Mentions ({len(session.todo_mentions)}) ---")
        for todo in session.todo_mentions:
            lines.append(f"  - {todo[:200]}")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> None:
    """CLI entry point: parse a JSONL file and print a summary."""
    if len(sys.argv) < 2:
        print(
            "Usage: python jsonl_parser.py <path-to-session.jsonl>",
            file=sys.stderr,
        )
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    if not transcript_path.is_file():
        print(f"Error: File not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    session = parse_session(transcript_path)
    print(_format_summary(session))


if __name__ == "__main__":
    main()
