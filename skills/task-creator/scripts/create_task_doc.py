#!/usr/bin/env python3
"""
Create a numbered task document from the project task template.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TASK_FILE_RE = re.compile(r"^(\d{3,})_.+\.md$")
TITLE_PLACEHOLDER_RE = re.compile(r"\*\*Title:\*\*\s*\[[^\]]*\]")
GOAL_PLACEHOLDER_RE = re.compile(r"\*\*Goal:\*\*\s*\[[^\]]*\]")
BUNDLED_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "task_template.md"
)


class ConfigError(Exception):
    """Configuration or layout error."""


class InputError(Exception):
    """Input parsing error."""


class WriteError(Exception):
    """Write failure error."""


@dataclass
class Resolution:
    project_root: Path
    ai_docs_root: Path
    template_path: Path
    tasks_dir: Path


def get_git_toplevel(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    return Path(raw).resolve()


def resolve_project_root(cwd: Path) -> Path:
    git_root = get_git_toplevel(cwd)
    if git_root is not None:
        return git_root
    return cwd.resolve()


def resolve_layout(project_root: Path, ai_docs_root_arg: str | None) -> Resolution:
    if ai_docs_root_arg:
        ai_docs_root = Path(ai_docs_root_arg).expanduser().resolve()
        template_path = ai_docs_root / "dev_templates" / "task_template.md"
        return Resolution(
            project_root=project_root,
            ai_docs_root=ai_docs_root,
            template_path=template_path,
            tasks_dir=ai_docs_root / "tasks",
        )

    ai_docs_root = project_root / "ai_docs"
    template_path = ai_docs_root / "dev_templates" / "task_template.md"
    return Resolution(
        project_root=project_root,
        ai_docs_root=ai_docs_root,
        template_path=template_path,
        tasks_dir=ai_docs_root / "tasks",
    )


def ensure_template(
    template_path: Path,
    allow_bootstrap: bool,
    dry_run: bool,
) -> bool:
    """
    Ensure template exists.

    Returns:
        True if template was bootstrapped (or would be bootstrapped in dry-run),
        False if template already existed.
    """
    if template_path.is_file():
        return False

    if not allow_bootstrap:
        raise ConfigError(
            "Missing /ai_docs/dev_templates/task_template.md and template "
            "bootstrapping is disabled (--no-bootstrap-template)."
        )

    if not BUNDLED_TEMPLATE_PATH.is_file():
        raise ConfigError(
            "Bundled fallback template is missing.\n"
            f"Expected:\n- {BUNDLED_TEMPLATE_PATH}"
        )

    if dry_run:
        return True

    try:
        template_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BUNDLED_TEMPLATE_PATH, template_path)
        return True
    except OSError as exc:
        raise WriteError(f"failed creating template {template_path}: {exc}") from exc


def sanitize_request_text(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return normalized


def derive_feature_text(request_text: str) -> str:
    cleaned = sanitize_request_text(request_text)
    if not cleaned:
        raise InputError("request text is empty")

    trigger_patterns = [
        re.compile(
            r"^(?:please\s+)?(?:help\s+me\s+(?:to\s+)?)?"
            r"(?:create|make|start)\s+(?:a\s+)?task(?:\s+document)?\s*(.*)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:please\s+)?new\s+task(?:\s+document)?\s*(.*)$",
            re.IGNORECASE,
        ),
    ]

    remainder = cleaned
    for pattern in trigger_patterns:
        match = pattern.match(cleaned)
        if match:
            remainder = match.group(1).strip()
            break

    if remainder.lower().startswith("for "):
        remainder = remainder[4:].strip()

    if not remainder:
        for_match = re.search(r"\bfor\s+(.+)$", cleaned, re.IGNORECASE)
        if for_match:
            remainder = for_match.group(1).strip()

    remainder = remainder.strip(" .,!?:;\"'")
    return remainder


def to_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text


def slugify(feature_text: str) -> str:
    ascii_text = to_ascii(feature_text).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        return "general_task"
    return slug


def title_from_slug(slug: str) -> str:
    parts = [p for p in slug.split("_") if p]
    if not parts:
        return "General Task"
    return " ".join(part.capitalize() for part in parts)


def build_goal_statement(title: str, slug: str) -> str:
    if slug == "general_task":
        return (
            "Define and document this task with clear scope, requirements, and "
            "execution steps using the project task template."
        )
    return (
        f"Implement {title.lower()} and document scope, requirements, and execution "
        "steps using the project task template."
    )


def next_task_number(tasks_dir: Path) -> int:
    max_seen = 0
    if not tasks_dir.exists():
        return 1
    for path in tasks_dir.iterdir():
        if not path.is_file():
            continue
        match = TASK_FILE_RE.match(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number > max_seen:
            max_seen = number
    return max_seen + 1 if max_seen > 0 else 1


def format_task_number(number: int) -> str:
    width = max(3, len(str(number)))
    return f"{number:0{width}d}"


def insert_generation_note(template_text: str, request_text: str) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    one_line_request = " ".join(request_text.split())
    safe_request = one_line_request.replace('"', "'")
    note = (
        f'> Generated on {date_str} by `task-creator` from request: "{safe_request}"'
    )

    lines = template_text.splitlines()
    if lines and lines[0].startswith("#"):
        return "\n".join([lines[0], "", note, ""] + lines[1:]) + "\n"
    return note + "\n\n" + template_text


def prefill_template(
    template_text: str,
    request_text: str,
    task_title: str,
    goal_statement: str,
) -> str:
    content = insert_generation_note(template_text, request_text)
    content = TITLE_PLACEHOLDER_RE.sub(f"**Title:** {task_title}", content, count=1)
    content = GOAL_PLACEHOLDER_RE.sub(f"**Goal:** {goal_statement}", content, count=1)
    return content


def atomic_write(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise WriteError(f"failed writing {path}: {exc}") from exc


def build_output(
    resolution: Resolution,
    number: int,
    filename: str,
    task_path: Path,
    title: str,
    goal: str,
    dry_run: bool,
    template_bootstrapped: bool,
) -> dict[str, object]:
    return {
        "project_root": str(resolution.project_root),
        "ai_docs_root": str(resolution.ai_docs_root),
        "template_path": str(resolution.template_path),
        "tasks_dir": str(resolution.tasks_dir),
        "task_number": number,
        "task_filename": filename,
        "task_path": str(task_path),
        "task_title": title,
        "goal_statement": goal,
        "template_bootstrapped": template_bootstrapped,
        "dry_run": dry_run,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a numbered task document from task_template.md.",
    )
    parser.add_argument(
        "--request-text",
        required=True,
        help="Original user request that triggered task creation.",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory used for project root discovery.",
    )
    parser.add_argument(
        "--ai-docs-root",
        help="Explicit ai_docs root override. Example: /path/to/ai_docs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute output and metadata without writing files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON output.",
    )
    parser.add_argument(
        "--no-bootstrap-template",
        action="store_true",
        help="Do not auto-create /ai_docs/dev_templates/task_template.md if missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        cwd = Path(args.cwd).expanduser().resolve()
        if not cwd.exists() or not cwd.is_dir():
            raise InputError(f"--cwd is not a directory: {cwd}")

        project_root = resolve_project_root(cwd)
        resolution = resolve_layout(project_root, args.ai_docs_root)
        template_bootstrapped = ensure_template(
            template_path=resolution.template_path,
            allow_bootstrap=not args.no_bootstrap_template,
            dry_run=args.dry_run,
        )

        feature_text = derive_feature_text(args.request_text)
        slug = slugify(feature_text)
        title = title_from_slug(slug)
        goal_statement = build_goal_statement(title, slug)

        number = next_task_number(resolution.tasks_dir)
        formatted_number = format_task_number(number)
        filename = f"{formatted_number}_{slug}.md"
        task_path = resolution.tasks_dir / filename

        if not args.dry_run:
            resolution.tasks_dir.mkdir(parents=True, exist_ok=True)
            template_text = resolution.template_path.read_text(encoding="utf-8")
            prefilled = prefill_template(
                template_text=template_text,
                request_text=args.request_text,
                task_title=title,
                goal_statement=goal_statement,
            )
            atomic_write(task_path, prefilled)

        payload = build_output(
            resolution=resolution,
            number=number,
            filename=filename,
            task_path=task_path,
            title=title,
            goal=goal_statement,
            dry_run=args.dry_run,
            template_bootstrapped=template_bootstrapped,
        )

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"project_root: {payload['project_root']}")
            print(f"ai_docs_root: {payload['ai_docs_root']}")
            print(f"template_path: {payload['template_path']}")
            print(f"tasks_dir: {payload['tasks_dir']}")
            print(f"task_number: {payload['task_number']}")
            print(f"task_filename: {payload['task_filename']}")
            print(f"task_path: {payload['task_path']}")
            print(f"task_title: {payload['task_title']}")
            print(f"goal_statement: {payload['goal_statement']}")
            print(f"template_bootstrapped: {payload['template_bootstrapped']}")
            print(f"dry_run: {payload['dry_run']}")
        return 0
    except ConfigError as exc:
        print(f"[CONFIG] {exc}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(f"[INPUT] {exc}", file=sys.stderr)
        return 3
    except WriteError as exc:
        print(f"[WRITE] {exc}", file=sys.stderr)
        return 4
    except OSError as exc:
        print(f"[WRITE] {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
