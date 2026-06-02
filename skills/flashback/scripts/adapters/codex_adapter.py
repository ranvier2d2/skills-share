#!/usr/bin/env python3
"""Codex runtime adapter for Flashback."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flashback_core import RESTART_PROMPT_STEM, _consolidate_memory, extract_pending_todos, find_task_files


class CodexAdapter:
    runtime_name = "codex"

    def discover_memory(self, repo_root: Path, memory_dir_arg: str | None, dry_run: bool) -> tuple[Path | None, list[str], list[str]]:
        files_read: list[str] = []
        warnings: list[str] = []

        candidates: list[Path] = []
        explicit = memory_dir_arg or os.environ.get("FLASHBACK_MEMORY_DIR")
        if explicit:
            explicit_path = Path(explicit).expanduser().resolve()
            explicit_memory = explicit_path / "MEMORY.md" if explicit_path.is_dir() else explicit_path
            if explicit_memory.exists():
                candidates.append(explicit_memory)
            elif memory_dir_arg and dry_run:
                warnings.append(
                    f"Explicit --memory-dir path does not exist: {explicit_memory}. "
                    "Provide a valid path or remove --memory-dir."
                )
                return None, files_read, warnings
            else:
                warnings.append(
                    f"Explicit memory path not found: {explicit_memory}. Falling back to default discovery."
                )

        candidates.extend(
            [
                (repo_root / "MEMORY.md").resolve(),
                (repo_root / "memory" / "MEMORY.md").resolve(),
                (repo_root / "ai_docs" / "MEMORY.md").resolve(),
            ]
        )

        for candidate in candidates:
            if candidate.exists():
                files_read.append(str(candidate))
                return candidate, files_read, warnings

        question = (
            "No memory file was discovered. Provide a memory directory/file path, "
            "or enter 'no' to bootstrap at <repo>/MEMORY.md"
        )

        if dry_run:
            warnings.append(question)
            return None, files_read, warnings

        if sys.stdin.isatty():
            user_input = input(f"{question}: ").strip()
            if user_input and user_input.lower() not in {"no", "n"}:
                user_path = Path(user_input).expanduser().resolve()
                if user_path.is_dir():
                    user_path = user_path / "MEMORY.md"
                files_read.append(str(user_path))
                return user_path, files_read, warnings

        bootstrap = (repo_root / "MEMORY.md").resolve()
        warnings.append(f"Memory file not found; bootstrapping {bootstrap}.")
        return bootstrap, files_read, warnings

    def read_task_state(self, repo_root: Path, memory_text: str, active_tasks: list[dict[str, str]]) -> tuple[list[str], list[str], list[str]]:
        task_files = find_task_files(repo_root, active_tasks)
        todos, files_read = extract_pending_todos(task_files)
        return todos, files_read, []

    def update_memory(self, memory_path: Path, out_file_hint: str, dry_run: bool) -> tuple[str, int, int, list[str], list[str], list[str]]:
        return _consolidate_memory(memory_path, out_file_hint, dry_run)

    def write_output(self, out_dir: Path, markdown_text: str, report_obj: dict, dry_run: bool) -> tuple[Path, Path, list[str]]:
        warnings: list[str] = []
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        base = out_dir / f"{RESTART_PROMPT_STEM}_{stamp}"

        markdown_path = base.with_suffix(".md")
        json_path = base.with_suffix(".json")

        suffix = 1
        while markdown_path.exists() or json_path.exists():
            markdown_path = out_dir / f"{RESTART_PROMPT_STEM}_{stamp}_{suffix:02d}.md"
            json_path = out_dir / f"{RESTART_PROMPT_STEM}_{stamp}_{suffix:02d}.json"
            suffix += 1

        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(markdown_text, encoding="utf-8")

        return markdown_path, json_path, warnings

    def copy_clipboard(self, content: str, disable_clipboard: bool) -> tuple[str, list[str]]:
        warnings: list[str] = []
        if disable_clipboard:
            return "skipped (--no-clipboard)", warnings

        if shutil.which("pbcopy") is None:
            warnings.append("pbcopy not available; clipboard copy skipped.")
            return "skipped (pbcopy unavailable)", warnings

        try:
            subprocess.run(["pbcopy"], input=content, text=True, check=True)
            return "copied", warnings
        except (subprocess.SubprocessError, OSError) as exc:
            warnings.append(f"Clipboard copy failed: {exc}")
            return f"failed: {exc}", warnings

    def probe_capabilities(self, repo_root: Path, memory_dir_arg: str | None) -> dict[str, bool]:
        memory_discovery = repo_root.exists() and repo_root.is_dir()
        safe_updates = os.access(repo_root, os.W_OK)
        output_generation = os.access(repo_root, os.W_OK)
        clipboard = shutil.which("pbcopy") is not None

        return {
            "memory_discovery": memory_discovery,
            "safe_updates": safe_updates,
            "output_generation": output_generation,
            "clipboard": clipboard,
            "task_state": True,
        }
