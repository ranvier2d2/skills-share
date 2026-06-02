#!/usr/bin/env python3
"""Validate output case bundle completeness and ordering rules."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import read_json, validate_annotation_review


REQUIRED_PATHS = [
    "manifest.json",
    "pages/raw",
    "pages/edited",
    "pages/edited/edit_manifest.json",
    "extractions/raw",
    "extractions/edited",
    "extractions/reconciled",
    "extractions/reconciled/reconciliation_report.json",
    "chronologies/legal_chronology.md",
    "chronologies/medical_chronology.md",
    "chronologies/legal_timeline.mmd",
    "chronologies/medical_timeline.mmd",
    "citations/citation_map.json",
    "qa/quality_report.md",
]

ORDERED_STAGES = [
    "render",
    "analyze_raw",
    "derive_edits",
    "review_edits",
    "apply_edits",
    "analyze_edited",
    "reconcile",
    "build_bundle",
]

REQUIRED_STAGES = [
    "render",
    "analyze_raw",
    "derive_edits",
    "apply_edits",
    "analyze_edited",
    "reconcile",
    "build_bundle",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate case bundle outputs.")
    parser.add_argument("--base-dir", required=True, help="Case base output directory")
    return parser.parse_args()


def extract_row_ids(md_path: Path) -> set[str]:
    text = md_path.read_text(encoding="utf-8")
    ids = set()
    for line in text.splitlines():
        if line.startswith("|"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if parts and re.match(r"^[A-Z]\d{3}$", parts[0]):
                ids.add(parts[0])
    return ids


def stage_order_ok(stages: list[dict[str, Any]]) -> bool:
    index_map = {name: i for i, name in enumerate(ORDERED_STAGES)}
    seen = [index_map[s["name"]] for s in stages if s.get("name") in index_map]
    return seen == sorted(seen)


def load_intents_file(base_dir: Path) -> Path | None:
    candidates = [
        base_dir / "edits" / "edit_intents_final.json",
        base_dir / "edits" / "edit_intents.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def validate_entity_bound_ops(intent_obj: dict[str, Any], errors: list[str]) -> None:
    required_entity_ops = {"draw_box", "draw_label", "redact_box"}
    for page in intent_obj.get("pages", []):
        page_id = str(page.get("page_id", "unknown"))
        for idx, op in enumerate(page.get("operations", []), start=1):
            op_name = str(op.get("op", ""))
            if op_name in required_entity_ops and not str(op.get("source_entity_id", "")).strip():
                errors.append(f"{page_id}:operation[{idx}] {op_name} missing source_entity_id")


def validate_citation_links(base_dir: Path, errors: list[str]) -> None:
    citations_path = base_dir / "citations" / "citation_map.json"
    legal_path = base_dir / "chronologies" / "legal_chronology.md"
    medical_path = base_dir / "chronologies" / "medical_chronology.md"
    all_events_path = base_dir / "chronologies" / "all_events_chronology.md"

    chronology_paths = [p for p in (legal_path, medical_path, all_events_path) if p.exists()]
    if not (citations_path.exists() and chronology_paths):
        return

    citation_map = read_json(citations_path)
    citation_rows = list(citation_map.get("citations", []))
    citation_index: dict[str, list[dict[str, Any]]] = {}
    for row in citation_rows:
        row_id = str(row.get("row_id", ""))
        citation_index.setdefault(row_id, []).append(row)

    all_row_ids: set[str] = set()
    for path in chronology_paths:
        all_row_ids.update(extract_row_ids(path))

    for row_id in sorted(all_row_ids):
        rows = citation_index.get(row_id, [])
        if not rows:
            errors.append(f"Chronology row has no citation mapping: {row_id}")
            continue
        valid_entity_link = any(
            str(item.get("entity_id", "")).strip()
            and str(item.get("entity_id", "")).strip().lower() != "missing"
            for item in rows
        )
        if not valid_entity_link:
            errors.append(f"Chronology row has no entity-linked citation: {row_id}")


def validate_review_mode(base_dir: Path, stages: list[dict[str, Any]], errors: list[str]) -> None:
    stage_map = {str(s.get("name")): s for s in stages}
    review_stage = stage_map.get("review_edits")
    if not review_stage:
        return

    review_details = dict(review_stage.get("details", {}))
    review_mode = str(review_details.get("review_mode", ""))
    audit_path = base_dir / "edits" / "review_audit.json"
    if not audit_path.exists():
        errors.append(f"Review stage present but audit file missing: {audit_path}")
        return

    audit_obj = read_json(audit_path)
    if not isinstance(audit_obj.get("rows"), list):
        errors.append("review_audit.json missing rows[]")

    review_file = audit_obj.get("review_file")
    if review_mode == "human_review":
        if not review_file:
            errors.append("review_edits recorded as human_review but review_file is missing")
            return
        review_path = Path(str(review_file)).expanduser().resolve()
        if not review_path.exists():
            errors.append(f"Human review file does not exist: {review_path}")
            return
        review_obj = read_json(review_path)
        review_errors = validate_annotation_review(review_obj)
        for err in review_errors:
            errors.append(f"annotation_review invalid: {err}")


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()

    errors: list[str] = []

    for rel in REQUIRED_PATHS:
        target = base_dir / rel
        if not target.exists():
            errors.append(f"Missing required output: {target}")

    manifest = read_json(base_dir / "manifest.json") if (base_dir / "manifest.json").exists() else {"stages": []}
    stages = list(manifest.get("stages", []))
    stage_names = [str(s.get("name")) for s in stages]

    if not stage_order_ok(stages):
        errors.append("Stage order invalid: vision-first ordering requirement is violated")
    for required in REQUIRED_STAGES:
        if required not in stage_names:
            errors.append(f"Missing stage in manifest: {required}")

    validate_citation_links(base_dir, errors)

    intents_path = load_intents_file(base_dir)
    if intents_path is None:
        errors.append("Missing edits/edit_intents_final.json (or fallback edit_intents.json)")
    else:
        intent_obj = read_json(intents_path)
        validate_entity_bound_ops(intent_obj, errors)

    validate_review_mode(base_dir, stages, errors)

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 2

    print(f"Bundle validation passed for {base_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
