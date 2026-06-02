# Examples

## Context PDF Delivery Adapter

Goal:

```text
Create PDFs from the root context glossary and the medicine context glossary.
```

Skill route:

```text
Goal
-> codex-goal-planner-skill-orchestrator
-> Context/PDF delivery practice
-> context_pdf_delivery_adapter.py
-> Proof Closure Semantics
-> Completion Audit
```

Executable adapter:

```bash
uv run python scripts/context_pdf_delivery_adapter.py --help
uv run python scripts/context_pdf_delivery_adapter.py inspect --json
uv run python scripts/context_pdf_delivery_adapter.py render --dry-run --json
uv run --with reportlab python scripts/context_pdf_delivery_adapter.py render --pdf --json
uv run --with reportlab python scripts/context_pdf_delivery_adapter.py verify outputs/context-pdfs/*.pdf --json
```

Completion evidence:

```text
delivery_ready=true
PDF artifacts exist
PDF filetype verified
page count verified
source coverage verified
manifest written
```

## Ableton Writer Mode Sketch

Goal:

```text
Write musical automation in Ableton.
```

Do not write directly from memory. Route through:

```text
Ableton Skill
-> Tool Policy
-> Musical Automation Mapping adapter
-> current snapshot
-> dry-run
-> queue
-> write
-> runtime reconciliation
```

Completion cannot be based on ACK alone. It needs Runtime Reconciliation and
domain evidence that the automation landed in the intended musical region.
