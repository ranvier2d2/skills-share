#!/usr/bin/env python3
import argparse
import pathlib
import re
import sys


def parse_phases(text):
    phase_re = re.compile(r"^##\s+.*\bPHASE\s+(\d+):\s*(.+)$", re.MULTILINE)
    matches = list(phase_re.finditer(text))
    phases = []

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        section = text[start:end]
        phase_num = match.group(1)
        phase_title = match.group(2).strip()

        status = "not_started"
        status_match = re.search(r"\*\*Status\*\*:\s*[^a-zA-Z]*([a-z_]+)", section)
        if status_match:
            status = status_match.group(1).lower()

        todo_blocks = list(re.finditer(r"^###\s+TODO\b", section, re.MULTILINE))
        todo_statuses = []
        for todo_idx, todo_match in enumerate(todo_blocks):
            todo_start = todo_match.end()
            todo_end = todo_blocks[todo_idx + 1].start() if todo_idx + 1 < len(todo_blocks) else len(section)
            todo_section = section[todo_start:todo_end]
            todo_status = "pending"
            todo_status_match = re.search(r"\*\*Status\*\*:\s*([a-z_]+)", todo_section)
            if todo_status_match:
                todo_status = todo_status_match.group(1).lower()
            todo_statuses.append(todo_status)

        subtask_matches = list(re.finditer(r"^\s*-\s*\[(x| )\]\s*\*\*SUB_", section, re.MULTILINE))
        subtask_total = len(subtask_matches)
        subtask_completed = sum(1 for m in subtask_matches if m.group(1) == "x")

        phases.append(
            {
                "num": phase_num,
                "title": phase_title,
                "status": status,
                "todo_statuses": todo_statuses,
                "subtask_total": subtask_total,
                "subtask_completed": subtask_completed,
            }
        )

    return phases


def format_summary(phases):
    status_emoji = {
        "completed": "🟢",
        "in_progress": "🟢",
        "not_started": "🟡",
        "blocked": "🔴",
    }

    lines = []
    for phase in phases:
        todo_total = len(phase["todo_statuses"])
        todo_done = sum(1 for s in phase["todo_statuses"] if s == "done")
        todo_in_progress = sum(1 for s in phase["todo_statuses"] if s == "in_progress")
        todo_blocked = sum(1 for s in phase["todo_statuses"] if s == "blocked")
        emoji = status_emoji.get(phase["status"], "🟡")
        label = f"Phase {phase['num']}: {phase['title']}"
        lines.append(
            "- **{label}** — Status: {emoji} {status}; TODOs: {todos}; Subtasks: {subtasks}; "
            "Completed: {done}; In Progress: {in_progress}; Blocked: {blocked}.".format(
                label=label,
                emoji=emoji,
                status=phase["status"],
                todos=todo_total,
                subtasks=phase["subtask_total"],
                done=todo_done,
                in_progress=todo_in_progress,
                blocked=todo_blocked,
            )
        )

    total_todos = sum(len(phase["todo_statuses"]) for phase in phases)
    total_subtasks = sum(phase["subtask_total"] for phase in phases)
    total_done = sum(1 for phase in phases for s in phase["todo_statuses"] if s == "done")
    total_in_progress = sum(
        1 for phase in phases for s in phase["todo_statuses"] if s == "in_progress"
    )
    total_blocked = sum(1 for phase in phases for s in phase["todo_statuses"] if s == "blocked")

    lines.append(
        "- **Total** — Status: 🟢 in_progress; TODOs: {todos}; Subtasks: {subtasks}; Completed: {done}; "
        "In Progress: {in_progress}; Blocked: {blocked}.".format(
            todos=total_todos,
            subtasks=total_subtasks,
            done=total_done,
            in_progress=total_in_progress,
            blocked=total_blocked,
        )
    )

    return lines


def replace_summary_block(text, summary_lines):
    lines = text.splitlines(keepends=True)
    summary_start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("##") and "Progress Summary" in line:
            summary_start = idx
            break

    if summary_start is None:
        raise ValueError("Progress Summary section not found")

    summary_end = None
    for idx in range(summary_start + 1, len(lines)):
        if lines[idx].startswith("### ") or lines[idx].startswith("## "):
            summary_end = idx
            break

    if summary_end is None:
        summary_end = len(lines)

    new_block = ["\n"]
    new_block.extend([f"{line}\n" for line in summary_lines])
    new_block.append("\n")

    return "".join(lines[: summary_start + 1] + new_block + lines[summary_end:])


def write_file_safely(path, content):
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def main():
    parser = argparse.ArgumentParser(description="Sync Progress Summary counts in PROGRESS.md")
    parser.add_argument("--path", default="PROGRESS.md", help="Path to PROGRESS.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if summary is up to date without modifying the file",
    )
    args = parser.parse_args()

    path = pathlib.Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    original = path.read_text(encoding="utf-8")
    phases = parse_phases(original)
    if not phases:
        print("error: no phase sections found", file=sys.stderr)
        return 1

    summary_lines = format_summary(phases)
    updated = replace_summary_block(original, summary_lines)

    if args.check:
        if updated != original:
            print("Progress Summary is out of sync. Run without --check to update.")
            return 1
        print("Progress Summary is up to date.")
        return 0

    if updated == original:
        print("Progress Summary is already up to date.")
        return 0

    write_file_safely(path, updated)
    print(f"Updated Progress Summary in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
