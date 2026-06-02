"""Runtime adapter registry for Flashback."""

from __future__ import annotations

from adapters.claude_adapter import ClaudeAdapter
from adapters.codex_adapter import CodexAdapter


def get_adapter(runtime: str):
    normalized = runtime.strip().lower()
    if normalized == "codex":
        return CodexAdapter()
    if normalized == "claude":
        return ClaudeAdapter()
    raise ValueError(f"Unsupported runtime '{runtime}'. Expected codex or claude.")
