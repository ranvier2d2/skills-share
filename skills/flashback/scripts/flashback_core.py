#!/usr/bin/env python3
"""Core workflow for Flashback session handoff generation."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

ACTIVE_STATUS_MARKERS = ("IN PROGRESS", "CURRENT FOCUS", "NOT STARTED")
DECISION_KEYWORDS = ("LOCKED", "DECIDED", "FROZEN", "RESOLVED")
PROTECTED_SECTION_KEYWORDS = (
    "invariant",
    "safety",
    "architecture",
    "architecture map",
)
MOVABLE_SECTIONS = {
    "task history": "task_history.md",
    "session notes": "session_notes.md",
    "working notes": "working_notes.md",
    "execution log": "execution_log.md",
    "findings": "findings.md",
    "scratchpad": "scratchpad.md",
    "observations": "observations.md",
}
RESTART_PROMPT_STEM = "flashback"


class RuntimeAdapter(Protocol):
    runtime_name: str

    def discover_memory(self, repo_root: Path, memory_dir_arg: str | None, dry_run: bool) -> tuple[Path | None, list[str], list[str]]:
        ...

    def read_task_state(self, repo_root: Path, memory_text: str, active_tasks: list[dict[str, str]]) -> tuple[list[str], list[str], list[str]]:
        ...

    def update_memory(self, memory_path: Path, out_file_hint: str, dry_run: bool) -> tuple[str, int, int, list[str], list[str], list[str]]:
        ...

    def write_output(self, out_dir: Path, markdown_text: str, report_obj: dict, dry_run: bool) -> tuple[Path, Path, list[str]]:
        ...

    def copy_clipboard(self, content: str, disable_clipboard: bool) -> tuple[str, list[str]]:
        ...

    def probe_capabilities(self, repo_root: Path, memory_dir_arg: str | None) -> dict[str, bool]:
        ...


@dataclass
class FlashbackInputs:
    mode: str
    summary: str | None
    repo_root: Path
    memory_dir_arg: str | None
    out_dir: Path
    disable_clipboard: bool = False
    dry_run: bool = False


@dataclass
class FlashbackRunResult:
    report: dict
    markdown_text: str
    markdown_path: Path
    json_path: Path
    summary_lines: list[str] = field(default_factory=list)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except OSError as exc:
        return 127, "", str(exc)


def _iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _stamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def _line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "notes"


def _parse_sections(text: str) -> list[dict]:
    lines = text.splitlines()
    sections: list[dict] = []
    starts: list[tuple[int, str, int]] = []
    for idx, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        starts.append((idx, title, level))

    if not starts:
        return sections

    for i, (start, title, level) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        body = lines[start + 1 : end]
        sections.append(
            {
                "title": title,
                "level": level,
                "start": start,
                "end": end,
                "heading": lines[start],
                "body": body,
                "size": max(0, end - start),
            }
        )
    return sections


def _is_protected_section(title: str) -> bool:
    lower = title.lower()
    return any(k in lower for k in PROTECTED_SECTION_KEYWORDS)


def _movable_filename_for_section(title: str) -> str | None:
    lower = title.lower()
    for key, filename in MOVABLE_SECTIONS.items():
        if key in lower:
            return filename
    return None


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 3:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        rows.append(cells)
    return rows


def parse_active_tasks(memory_text: str) -> list[dict[str, str]]:
    rows = _table_rows(memory_text.splitlines())
    tasks: list[dict[str, str]] = []
    seen_task_ids: set[str] = set()

    # Pass 1: markdown table rows (original logic)
    for cells in rows:
        if len(cells) < 3:
            continue
        first, second, third = cells[0], cells[1], cells[2]
        if first.lower() == "task" and second.lower() == "status":
            continue
        status_upper = second.upper()
        if any(marker in status_upper for marker in ACTIVE_STATUS_MARKERS):
            tasks.append({"task": first, "status": second, "next_action": third})
            tid = parse_task_id(first)
            if tid:
                seen_task_ids.add(tid)

    # Pass 2: bullet-point format (e.g. "- Task 020: Description — STATUS")
    # Lines may have multiple em-dash segments, so split by — and find the status segment.
    bullet_task_re = re.compile(r"^\s*[-*]\s+Task\s+(\d{3,})\b", flags=re.IGNORECASE)
    for line in memory_text.splitlines():
        m = bullet_task_re.match(line)
        if not m:
            continue
        task_id = m.group(1)
        if task_id in seen_task_ids:
            continue

        # Split by em-dash and check each segment (right to left) for status markers
        parts = line.split("\u2014")  # U+2014 = —
        status_raw = ""
        next_action = ""
        for i, part in enumerate(parts[1:], start=1):
            part_stripped = part.strip()
            part_upper = part_stripped.upper()
            if any(marker in part_upper for marker in ACTIVE_STATUS_MARKERS):
                status_raw = part_stripped
                if i + 1 < len(parts):
                    next_action = "\u2014".join(parts[i + 1 :]).strip()
                break

        if not status_raw:
            continue

        # Extract the full task label from the first segment
        label_m = re.search(r"Task\s+\d{3,}[^\u2014]*", line, flags=re.IGNORECASE)
        task_label = label_m.group(0).strip() if label_m else f"Task {task_id}"
        tasks.append({"task": task_label, "status": status_raw, "next_action": next_action})
        seen_task_ids.add(task_id)

    # Pass 3: "next task" style lines (e.g. "- **Next task to start**: Task 024")
    next_task_re = re.compile(r"next\s+task", flags=re.IGNORECASE)
    task_id_re = re.compile(r"Task\s+(\d{3,})")
    for line in memory_text.splitlines():
        if not next_task_re.search(line):
            continue
        m = task_id_re.search(line)
        if not m or m.group(1) in seen_task_ids:
            continue
        task_label = f"Task {m.group(1)}"
        clean_line = re.sub(r"^\s*[-*]\s+", "", line).strip().replace("**", "")
        tasks.append({"task": task_label, "status": "PLANNED (next)", "next_action": clean_line})
        seen_task_ids.add(m.group(1))

    return tasks


def detect_decisions(text_blobs: list[str]) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    seen: set[str] = set()

    table_row_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*$")
    # Strict structured keyword regex: requires KEYWORD: or **KEYWORD**: format
    structured_kw_re = re.compile(
        r"(?:\*\*)?(" + "|".join(DECISION_KEYWORDS) + r")(?:\*\*)?\s*:",
        flags=re.IGNORECASE,
    )

    for blob in text_blobs:
        for raw in blob.splitlines():
            line = raw.strip()
            if not line:
                continue
            tm = table_row_re.match(line)
            if tm:
                decision = tm.group(1).strip()
                rationale = tm.group(2).strip()
                date_s = tm.group(3).strip()
                key = f"{decision}|{rationale}|{date_s}"
                if key not in seen and decision.lower() != "decision":
                    seen.add(key)
                    decisions.append({"decision": decision, "rationale": rationale, "date": date_s})
                continue

            # Pass 2: keyword detection — strict structured format only.
            if structured_kw_re.search(line):
                # Skip structural / noisy lines even if they match the pattern
                if (
                    line.startswith("- [")       # markdown links like "- [locked-decisions.md](...)"
                    or line.startswith("#")       # section headings
                    or "](" in line               # inline markdown links
                    or re.match(r"^\|[-\s:|]+\|$", line)  # table separator rows
                    or re.match(r"^\d+\.\s", line)         # numbered list items ("5. Read MEMORY.md...")
                    or re.search(r"memory/|MEMORY\.md|memory file", line, re.IGNORECASE)
                    or (
                        re.search(r"resolved to\b", line, re.IGNORECASE)
                        and not re.search(r"RESOLVED\s*:", line)
                    )
                ):
                    continue
                if len(line) > 180:
                    line = line[:177] + "..."
                key = f"{line}|{_iso_now()}"
                if key not in seen:
                    seen.add(key)
                    decisions.append({"decision": line, "rationale": "Captured from session notes", "date": _iso_now()})

    return decisions


def parse_task_id(task_label: str) -> str | None:
    m = re.search(r"(\d{3,})", task_label)
    if not m:
        return None
    return m.group(1)


def find_task_files(repo_root: Path, active_tasks: list[dict[str, str]]) -> list[Path]:
    task_dir = repo_root / "ai_docs" / "tasks"
    if not task_dir.exists():
        return []

    matched: list[Path] = []
    for task in active_tasks:
        task_id = parse_task_id(task.get("task", ""))
        if not task_id:
            continue
        candidates = sorted(task_dir.glob(f"{task_id}_*.md"))
        if candidates:
            matched.append(candidates[0])
    return matched


def summarize_git_state(repo_root: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    details: list[str] = []

    code, out, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    if code != 0 or out.lower() != "true":
        warnings.append("Repository is not a git work tree; skipped git state checks.")
        return warnings, details

    log_cmd = ["git", "log", "--oneline", '--since=12 hours ago']
    code, out, _ = _run(log_cmd, cwd=repo_root)
    if code == 0 and out.strip():
        details.append("Recent commits (12h):")
        details.extend(f"- {line}" for line in out.splitlines()[:5])
    else:
        code2, out2, _ = _run(["git", "log", "--oneline", '--since=24 hours ago'], cwd=repo_root)
        if code2 == 0 and out2.strip():
            details.append("Recent commits (24h):")
            details.extend(f"- {line}" for line in out2.splitlines()[:5])
        else:
            details.append("No commits found in the last 24 hours.")

    code, status_out, _ = _run(["git", "status", "--short"], cwd=repo_root)
    if code == 0 and status_out.strip():
        modified = 0
        untracked = 0
        for line in status_out.splitlines():
            if line.startswith("??"):
                untracked += 1
            else:
                modified += 1
        warnings.append(f"Uncommitted changes detected: {modified} modified/staged, {untracked} untracked files.")

    code, diff_out, _ = _run(["git", "diff", "--stat"], cwd=repo_root)
    if code == 0 and diff_out.strip():
        details.append("Working tree diff summary:")
        details.extend(f"- {line}" for line in diff_out.splitlines()[:8])

    code, staged_out, _ = _run(["git", "diff", "--staged", "--stat"], cwd=repo_root)
    if code == 0 and staged_out.strip():
        details.append("Staged diff summary:")
        details.extend(f"- {line}" for line in staged_out.splitlines()[:8])

    return warnings, details


def extract_pending_todos(paths: list[Path]) -> tuple[list[str], list[str]]:
    todos: list[str] = []
    files_read: list[str] = []
    todo_re = re.compile(r"^\s*[-*]\s*\[\s*\]\s+(.+)$")

    for path in paths:
        if not path.exists():
            continue
        files_read.append(str(path))
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            m = todo_re.match(line)
            if m:
                todo = m.group(1).strip()
                if len(todo) > 200:
                    todo = todo[:197] + "..."
                todos.append(f"{path.name}: {todo}")

    unique: list[str] = []
    seen: set[str] = set()
    for item in todos:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique[:20], files_read


def _list_memory_related_files(memory_path: Path) -> list[Path]:
    memory_dir = memory_path.parent
    files = [memory_path]
    for extra in sorted(memory_dir.glob("*.md")):
        if extra == memory_path:
            continue
        files.append(extra)
    return files


def _derive_accomplishments(
    summary: str | None,
    active_tasks: list[dict[str, str]],
    git_details: list[str],
    decisions: list[dict[str, str]],
) -> list[str]:
    if summary:
        lines = [line.strip(" -") for line in summary.splitlines() if line.strip()]
        if not lines:
            lines = [summary.strip()]
        return lines[:5]

    accomplishments: list[str] = []
    if active_tasks:
        accomplishments.append(f"Reviewed {len(active_tasks)} active tasks and immediate next actions.")
    if decisions:
        accomplishments.append(f"Captured {len(decisions)} locked decisions for restart continuity.")
    if git_details:
        accomplishments.append("Captured current git state (recent commits and diff summaries).")
    accomplishments.append("Generated a self-contained restart prompt with ordered file-read guidance.")
    return accomplishments[:5]


def _build_files_to_read(memory_path: Path, task_files: list[Path]) -> list[tuple[str, str]]:
    files = [(str(memory_path), "Primary project memory state")]
    for task_file in task_files:
        files.append((str(task_file), "Active task context and TODOs"))
    return files[:6]


def _build_immediate_next_action(
    active_tasks: list[dict[str, str]],
    todos: list[str],
    memory_text: str = "",
) -> str:
    for task in active_tasks:
        next_action = task.get("next_action", "").strip()
        if next_action:
            return f"{task.get('task', 'Active task')}: {next_action}"
    if todos:
        return f"Address highest-priority pending TODO: {todos[0]}"
    # Scan memory for explicit "next task" or "next:" hints before falling back
    if memory_text:
        for line in memory_text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if "next task" in lower or "next:" in lower:
                # Remove leading markdown formatting (bullets, headers, bold)
                cleaned = stripped.lstrip("#*->• ").strip()
                # Strip bold markers
                cleaned = cleaned.replace("**", "")
                if cleaned:
                    return cleaned
    return "Read MEMORY.md and continue the highest-priority active task with a single concrete next step."


def _format_locked_decisions(decisions: list[dict[str, str]]) -> str:
    if not decisions:
        return ""
    out = [
        "## Locked Decisions (Do Not Re-Litigate)",
        "| Decision | Rationale | Date |",
        "|----------|-----------|------|",
    ]
    for item in decisions[:20]:
        d = item.get("decision", "").replace("|", "/")
        r = item.get("rationale", "").replace("|", "/")
        date_s = item.get("date", _iso_now())
        out.append(f"| {d} | {r} | {date_s} |")
    return "\n".join(out)


def _format_active_tasks(active_tasks: list[dict[str, str]]) -> str:
    if not active_tasks:
        return "No active tasks found in memory."
    out = [
        "| Task | Status | Next Action |",
        "|------|--------|-------------|",
    ]
    for task in active_tasks:
        out.append(
            "| {task} | {status} | {next_action} |".format(
                task=task.get("task", "").replace("|", "/"),
                status=task.get("status", "").replace("|", "/"),
                next_action=task.get("next_action", "").replace("|", "/"),
            )
        )
    return "\n".join(out)


def _build_restart_prompt(
    project_name: str,
    version: str,
    accomplishments: list[str],
    decisions: list[dict[str, str]],
    active_tasks: list[dict[str, str]],
    todos: list[str],
    immediate_next: str,
    files_to_read: list[tuple[str, str]],
    warnings: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"I'm continuing work on {project_name} ({version}).")
    lines.append("")
    lines.append("Read your memory files to orient, then here's the session context:")
    lines.append("")
    lines.append("## What Was Accomplished Last Session")
    for bullet in accomplishments[:5]:
        lines.append(f"- {bullet}")

    locked = _format_locked_decisions(decisions)
    if locked:
        lines.append("")
        lines.append(locked)

    lines.append("")
    lines.append("## Active Tasks")
    lines.append(_format_active_tasks(active_tasks))

    lines.append("")
    lines.append("## Pending TODOs")
    if todos:
        for todo in todos[:20]:
            lines.append(f"- {todo}")
    else:
        lines.append("- No pending TODOs detected from active task files.")

    lines.append("")
    lines.append("## Immediate Next Action")
    lines.append(immediate_next)

    lines.append("")
    lines.append("## Files to Read First (in order)")
    for idx, (path, why) in enumerate(files_to_read, start=1):
        lines.append(f"{idx}. `{path}` — {why}")

    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No blocking warnings detected.")

    lines.append("")
    lines.append("Don't start executing yet — read the referenced files first, then confirm your understanding before proceeding.")

    return "\n".join(lines) + "\n"


def _update_quick_links(memory_text: str, rel_paths: list[str]) -> str:
    if not rel_paths:
        return memory_text

    lines = memory_text.splitlines()
    for idx, line in enumerate(lines):
        if re.match(r"^##\s+Quick Links\s*$", line.strip(), flags=re.IGNORECASE):
            insert_at = idx + 1
            while insert_at < len(lines) and not lines[insert_at].startswith("## "):
                insert_at += 1
            existing_block = "\n".join(lines[idx + 1 : insert_at])
            new_lines: list[str] = []
            for rel in rel_paths:
                entry = f"- `{rel}`"
                if entry not in existing_block:
                    new_lines.append(entry)
            if new_lines:
                lines[insert_at:insert_at] = new_lines
            return "\n".join(lines) + ("\n" if memory_text.endswith("\n") else "")

    append_block = ["", "## Quick Links"]
    append_block.extend(f"- `{rel}`" for rel in rel_paths)
    return memory_text.rstrip() + "\n" + "\n".join(append_block) + "\n"


def _consolidate_memory(memory_path: Path, output_link: str, dry_run: bool) -> tuple[str, int, int, list[str], list[str], list[str]]:
    created: list[str] = []
    updated: list[str] = []
    warnings: list[str] = []

    if not memory_path.exists():
        bootstrap = (
            "# Project Memory\n\n"
            "## Current Focus\n"
            "- Add current focus here.\n\n"
            "## Task Status\n"
            "| Task | Status | Next Action |\n"
            "|------|--------|-------------|\n"
            "| 000: Bootstrap | IN PROGRESS | Fill task context and run flashback again |\n"
        )
        before = 0
        after = _line_count(bootstrap)
        if not dry_run:
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text(bootstrap, encoding="utf-8")
            created.append(str(memory_path))
        return bootstrap, before, after, created, updated, warnings

    original = memory_path.read_text(encoding="utf-8", errors="ignore")
    before = _line_count(original)
    text = original

    sections = _parse_sections(text)
    moved_rel_paths: list[str] = []

    if before > 180:
        move_candidates = [
            section
            for section in sections
            if not _is_protected_section(section["title"]) and _movable_filename_for_section(section["title"])
        ]
        if move_candidates:
            target = sorted(move_candidates, key=lambda item: item["size"], reverse=True)[0]
            filename = _movable_filename_for_section(target["title"]) or f"{_safe_slug(target['title'])}.md"
            detail_path = memory_path.parent / filename

            title_line = f"# {target['title']} - Detailed Notes"
            preface = "Moved from MEMORY.md to keep it under 200 lines. See MEMORY.md for summary."
            imported = f"\n\n## Imported {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

            moved_content = "\n".join([target["heading"], *target["body"]]).strip()
            detail_text = "\n".join([title_line, "", preface]) + imported + moved_content + "\n"

            lines = text.splitlines()
            replacement = [
                target["heading"],
                f"Summary moved to `{filename}` on {_iso_now()} to enforce memory budget.",
            ]
            new_lines = lines[: target["start"]] + replacement + lines[target["end"] :]
            text = "\n".join(new_lines).rstrip() + "\n"

            if not dry_run:
                if detail_path.exists():
                    existing = detail_path.read_text(encoding="utf-8", errors="ignore")
                    detail_path.write_text(existing.rstrip() + "\n" + imported + moved_content + "\n", encoding="utf-8")
                    updated.append(str(detail_path))
                else:
                    detail_path.write_text(detail_text, encoding="utf-8")
                    created.append(str(detail_path))
                moved_rel_paths.append(filename)

            warnings.append(f"MEMORY.md exceeded 180 lines; moved section '{target['title']}' to {filename}.")
        else:
            warnings.append("MEMORY.md exceeded 180 lines but no allowlisted movable section was found.")

    checkpoint_header = "## Flashback Checkpoints"
    checkpoint_entry = f"- {_iso_now()} `{output_link}`"
    if checkpoint_header in text:
        if checkpoint_entry not in text:
            lines = text.splitlines()
            idx = lines.index(checkpoint_header)
            insert_at = idx + 1
            while insert_at < len(lines) and not lines[insert_at].startswith("## "):
                insert_at += 1
            lines.insert(insert_at, checkpoint_entry)
            text = "\n".join(lines).rstrip() + "\n"
    else:
        text = text.rstrip() + f"\n\n{checkpoint_header}\n{checkpoint_entry}\n"

    text = _update_quick_links(text, moved_rel_paths)
    after = _line_count(text)

    if not dry_run and text != original:
        memory_path.write_text(text, encoding="utf-8")
        updated.append(str(memory_path))

    if after >= 200:
        warnings.append(f"MEMORY.md line count is {after}, above recommended maximum of 200.")
    elif after >= 180:
        warnings.append(f"MEMORY.md line count is {after}, warning threshold reached (180+).")

    return text, before, after, created, updated, warnings


def _read_project_metadata(repo_root: Path) -> tuple[str, str]:
    pyproject = repo_root / "pyproject.toml"
    project_name = repo_root.name
    version = "unknown-version"

    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        name_m = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        ver_m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        if name_m:
            project_name = name_m.group(1)
        if ver_m:
            version = ver_m.group(1)

    # Fallback: package.json for Node/TypeScript projects
    if project_name == repo_root.name and version == "unknown-version":
        pkg_json = repo_root / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
                project_name = pkg.get("name", project_name)
                version = pkg.get("version", version)
            except (json.JSONDecodeError, OSError):
                pass

    return project_name, version


def run_flashback(adapter: RuntimeAdapter, inputs: FlashbackInputs) -> FlashbackRunResult:
    repo_root = inputs.repo_root.resolve()
    out_dir = inputs.out_dir.resolve()
    warnings: list[str] = []
    files_read: list[str] = []
    files_updated: list[str] = []
    created_files: list[str] = []

    probe = adapter.probe_capabilities(repo_root, inputs.memory_dir_arg)
    required = ("memory_discovery", "safe_updates", "output_generation")
    degraded = False
    missing = [cap for cap in required if not probe.get(cap, False)]
    if missing:
        degraded = True
        warnings.append(
            "Adapter missing required capabilities; switching to degraded mode: " + ", ".join(sorted(missing))
        )

    memory_path, discover_read, discover_warnings = adapter.discover_memory(repo_root, inputs.memory_dir_arg, inputs.dry_run)
    files_read.extend(discover_read)
    warnings.extend(discover_warnings)

    if memory_path is None:
        message = (
            "Memory file was not discovered. Provide --memory-dir, set FLASHBACK_MEMORY_DIR, "
            "or create one of: <repo>/MEMORY.md, <repo>/memory/MEMORY.md, <repo>/ai_docs/MEMORY.md"
        )
        if inputs.dry_run:
            raise RuntimeError(message)
        warnings.append(message)
        memory_path = repo_root / "MEMORY.md"

    output_filename_hint = f"output/flashback/{RESTART_PROMPT_STEM}_{_stamp_now()}.md"

    if inputs.mode == "quick" or degraded:
        if memory_path.exists():
            memory_text = memory_path.read_text(encoding="utf-8", errors="ignore")
            before_lines = _line_count(memory_text)
            after_lines = before_lines
            files_read.append(str(memory_path))
        else:
            memory_text = ""
            before_lines = 0
            after_lines = 0
    else:
        memory_text, before_lines, after_lines, created, updated, consolidate_warnings = adapter.update_memory(
            memory_path,
            output_filename_hint,
            inputs.dry_run,
        )
        created_files.extend(created)
        files_updated.extend(updated)
        warnings.extend(consolidate_warnings)
        files_read.append(str(memory_path))

    active_tasks = parse_active_tasks(memory_text)
    task_files = find_task_files(repo_root, active_tasks)

    # Fallback: when no active tasks were parsed, discover the most recently modified task files
    if not active_tasks and not task_files:
        task_dir = repo_root / "ai_docs" / "tasks"
        if task_dir.exists():
            all_task_files = sorted(task_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            # Filter out task files that are clearly done by checking their first 20 lines
            done_markers = {"done", "complete", "completed", "closed"}
            not_done: list[Path] = []
            for tf in all_task_files:
                try:
                    head = ""
                    with tf.open(encoding="utf-8", errors="ignore") as fh:
                        head_lines: list[str] = []
                        for i, line in enumerate(fh):
                            if i >= 20:
                                break
                            head_lines.append(line)
                        head = " ".join(head_lines).lower()
                except OSError:
                    continue
                if not any(marker in head for marker in done_markers):
                    not_done.append(tf)
            task_files = not_done[:3] if not_done else all_task_files[:3]

    for path in task_files:
        files_read.append(str(path))

    pending_todos, task_read_files, task_warnings = adapter.read_task_state(repo_root, memory_text, active_tasks)
    files_read.extend(task_read_files)
    warnings.extend(task_warnings)

    all_memory_files = _list_memory_related_files(memory_path) if memory_path.exists() else [memory_path]
    memory_blobs: list[str] = []
    for file_path in all_memory_files[:20]:
        if not file_path.exists():
            continue
        files_read.append(str(file_path))
        memory_blobs.append(file_path.read_text(encoding="utf-8", errors="ignore"))

    for task_file in task_files:
        if task_file.exists():
            memory_blobs.append(task_file.read_text(encoding="utf-8", errors="ignore"))

    decisions = detect_decisions(memory_blobs)

    git_warnings, git_details = summarize_git_state(repo_root)
    warnings.extend(git_warnings)

    project_name, version = _read_project_metadata(repo_root)
    accomplishments = _derive_accomplishments(inputs.summary, active_tasks, git_details, decisions)
    files_to_read = _build_files_to_read(memory_path, task_files)
    immediate_next = _build_immediate_next_action(active_tasks, pending_todos, memory_text)

    prompt_text = _build_restart_prompt(
        project_name=project_name,
        version=version,
        accomplishments=accomplishments,
        decisions=decisions,
        active_tasks=active_tasks,
        todos=pending_todos,
        immediate_next=immediate_next,
        files_to_read=files_to_read,
        warnings=warnings,
    )

    report_obj = {
        "mode": inputs.mode,
        "memory_line_count_before": before_lines,
        "memory_line_count_after": after_lines,
        "active_tasks": active_tasks,
        "pending_todos": pending_todos,
        "decisions": decisions,
        "warnings": sorted(set(warnings)),
        "files_read": sorted(set(files_read)),
        "files_updated": sorted(set(files_updated + created_files)),
        "output_file": "",
        "clipboard_status": "skipped",
        "adapter_runtime": adapter.runtime_name,
        "degraded_mode": degraded,
        "capability_probe": probe,
    }

    markdown_path, json_path, write_warnings = adapter.write_output(out_dir, prompt_text, report_obj, inputs.dry_run)
    warnings.extend(write_warnings)

    clipboard_status, clipboard_warnings = adapter.copy_clipboard(prompt_text, inputs.disable_clipboard)
    warnings.extend(clipboard_warnings)

    report_obj["warnings"] = sorted(set(warnings))
    report_obj["output_file"] = str(markdown_path)
    report_obj["clipboard_status"] = clipboard_status

    if not inputs.dry_run:
        json_path.write_text(json.dumps(report_obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_lines = [
        "FLASHBACK COMPLETE",
        f"Runtime: {adapter.runtime_name}",
        f"Mode: {inputs.mode}{' (degraded)' if degraded else ''}",
        f"Memory lines: {before_lines} -> {after_lines}",
        f"Restart prompt: {markdown_path}",
        f"Run report: {json_path}",
        f"Clipboard: {clipboard_status}",
        f"Active tasks: {len(active_tasks)}",
        f"Pending TODOs: {len(pending_todos)}",
        f"Decisions: {len(decisions)}",
    ]

    if report_obj["warnings"]:
        summary_lines.append("Warnings:")
        for warning in report_obj["warnings"][:8]:
            summary_lines.append(f"- {warning}")

    summary_lines.append("To restart: paste the generated markdown into a fresh session.")

    return FlashbackRunResult(
        report=report_obj,
        markdown_text=prompt_text,
        markdown_path=markdown_path,
        json_path=json_path,
        summary_lines=summary_lines,
    )


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(p) for p in parts)
