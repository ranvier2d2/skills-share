---
name: task-creator
description: Create numbered task documents from project templates when users ask to "create task", "new task", "make task", "create task document", or "create task for ...". Use /ai_docs only, auto-create task_template.md when missing, assign the next sequential number, prefill title and goal from the request, and then continue the template workflow.
---

# Task Creator Skill

## Purpose
Create numbered task documents deterministically from the project template, then hand off to the template's workflow.

## Quick Start

Run these commands from the target project repo. Set `TASK_CREATOR_SKILL_ROOT` to the installed `task-creator` skill root so the script can update the target repo while still loading bundled skill assets.

1. Run a dry-run first to confirm computed paths and filename:

```bash
uv run python $TASK_CREATOR_SKILL_ROOT/scripts/create_task_doc.py \
  --request-text "create task for adding email notifications" \
  --json --dry-run
```

2. Create the task file:

```bash
uv run python $TASK_CREATOR_SKILL_ROOT/scripts/create_task_doc.py \
  --request-text "create task for adding email notifications" \
  --json
```

3. Report the created file path and summary to the user.
4. Continue with section 16 workflow only after user confirmation.

## Workflow

### Step 1: Resolve Project and Task Layout
- Use script defaults whenever possible.
- Script default path:
  - `<project_root>/ai_docs`
- The script discovers `project_root` via `git rev-parse --show-toplevel`, then falls back to `--cwd`.
- Override explicitly with `--ai-docs-root` when needed.

### Step 2: Compute Number, Slug, and Paths
- Numbered files follow `^(\d{3,})_.+\.md$`.
- Next number is `max + 1`; if none found, start at `001`.
- Slug uses lowercase snake_case.
- Fallback slug is `general_task`.

### Step 3: Prefill Template Deterministically
- Require template at `<ai_docs_root>/dev_templates/task_template.md`.
- If missing, auto-bootstrap from bundled skill template at
  `$TASK_CREATOR_SKILL_ROOT/assets/task_template.md`.
- Use `<ai_docs_root>/tasks` for output and create the directory if missing.
- Prefill:
  - first `**Title:** [...]`
  - first `**Goal:** [...]`
- Insert a generation note with date and source request near the top.
- Write atomically unless `--dry-run`.

### Step 4: Continue Template Workflow
- After file creation, summarize:
  - selected `ai_docs_root`
  - created task path
  - assigned task number
  - prefilled title/goal
- Continue with section 16 only after user confirmation.

## Key Points

- Always run dry-run before writing when path ambiguity is possible.
- Never bypass the script for numbering or path selection.
- Keep creation deterministic; avoid ad-hoc shell snippets.

## Script Interface

### Required
- `--request-text "<original user request>"`

### Optional
- `--cwd "<path>"` (default: current working directory)
- `--ai-docs-root "<path>"` (explicit override)
- `--dry-run` (compute only)
- `--json` (structured output)
- `--no-bootstrap-template` (fail instead of creating missing template)

### Exit Codes
- `0` success
- `2` path/template configuration failure
- `3` invalid input
- `4` file write failure

## Success Criteria

- Task file created with correct sequential number.
- Task file created in the resolved `tasks` directory.
- Title and goal prefilled from user request.
- Deterministic JSON output available for automation.
- Template workflow starts only after user confirms.
