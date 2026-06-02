#!/usr/bin/env python3
"""Resolve edit intents into final intents using optional human review input."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import operation_order_key, read_json, upsert_stage, validate_annotation_review, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review annotation intents and emit final intents.")
    parser.add_argument("--edit-intents", required=True, help="Input edit_intents.json path")
    parser.add_argument("--out", required=True, help="Output edit_intents_final.json path")
    parser.add_argument(
        "--review-file",
        default=None,
        help="Optional annotation_review.json with explicit approvals/rejections/overrides",
    )
    parser.add_argument(
        "--audit-out",
        default=None,
        help="Optional output path for review audit report (default: edits/review_audit.json)",
    )
    parser.add_argument(
        "--auto-apply-threshold",
        type=float,
        default=0.75,
        help="Minimum confidence applied automatically when no explicit approval exists",
    )
    parser.add_argument("--base-dir", default=None, help="Optional case base directory")
    return parser.parse_args()


def apply_bbox_override(op: dict[str, Any], override_bbox: dict[str, Any]) -> dict[str, Any]:
    updated = dict(op)
    params = dict(updated.get("params", {}))

    for key in ("x", "y", "w", "h"):
        if key in override_bbox:
            params[key] = int(float(override_bbox[key]))
    if "target_bbox" in params and isinstance(params["target_bbox"], dict):
        target_bbox = dict(params["target_bbox"])
        for key in ("x", "y", "w", "h"):
            if key in override_bbox:
                target_bbox[key] = int(float(override_bbox[key]))
        params["target_bbox"] = target_bbox

    updated["params"] = params
    return updated


def main() -> int:
    args = parse_args()
    intents_path = Path(args.edit_intents).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    if not intents_path.exists():
        raise SystemExit(f"Edit intents not found: {intents_path}")

    intents_obj = read_json(intents_path)
    pages = list(intents_obj.get("pages", []))
    review_file = Path(args.review_file).expanduser().resolve() if args.review_file else None
    review_obj = {}

    approved_entities: set[str] = set()
    rejected_entities: set[str] = set()
    bbox_overrides: dict[str, dict[str, Any]] = {}

    if review_file:
        if not review_file.exists():
            raise SystemExit(f"Review file not found: {review_file}")
        review_obj = read_json(review_file)
        review_errors = validate_annotation_review(review_obj)
        if review_errors:
            for err in review_errors:
                print(f"ERROR: {err}")
            raise SystemExit("annotation_review failed validation")

        approved_entities = {str(x) for x in review_obj.get("approved_entities", [])}
        rejected_entities = {str(x) for x in review_obj.get("rejected_entities", [])}
        for item in review_obj.get("bbox_overrides", []):
            if isinstance(item, dict) and item.get("entity_id") and isinstance(item.get("bbox"), dict):
                bbox_overrides[str(item["entity_id"])] = dict(item["bbox"])

    kept_count = 0
    skipped_count = 0
    overridden_count = 0
    audit_rows = []
    final_pages = []

    for page in sorted(pages, key=lambda x: str(x.get("page_id", ""))):
        operations = sorted(list(page.get("operations", [])), key=operation_order_key)
        final_ops = []

        for op in operations:
            entity_id = str(op.get("source_entity_id", "")).strip()
            confidence = float(op.get("confidence", 0.0))
            requires_review = bool(op.get("requires_review", False))
            decision = "skip_low_confidence"
            keep = False

            if entity_id and entity_id in rejected_entities:
                decision = "rejected_by_review"
                keep = False
            elif entity_id and entity_id in approved_entities:
                decision = "approved_by_review"
                keep = True
            elif not requires_review and confidence >= float(args.auto_apply_threshold):
                decision = "auto_keep_high_confidence"
                keep = True
            elif review_file is None and requires_review:
                decision = "auto_skip_requires_review"
                keep = False
            elif review_file is not None and requires_review:
                decision = "review_required_not_approved"
                keep = False

            op_out = dict(op)
            if keep and entity_id in bbox_overrides:
                op_out = apply_bbox_override(op_out, bbox_overrides[entity_id])
                overridden_count += 1
                decision = f"{decision}_with_bbox_override"

            if keep:
                final_ops.append(op_out)
                kept_count += 1
            else:
                skipped_count += 1

            audit_rows.append(
                {
                    "page_id": page.get("page_id"),
                    "op": op.get("op"),
                    "source_entity_id": entity_id,
                    "confidence": confidence,
                    "requires_review": requires_review,
                    "decision": decision,
                }
            )

        final_pages.append(
            {
                "page_id": page.get("page_id"),
                "input_filename": page.get("input_filename"),
                "operations": final_ops,
            }
        )

    out_obj = {
        "case_id": intents_obj.get("case_id", "UNKNOWN_CASE"),
        "generated_from": "reviewed_intents" if review_file else "auto_filtered_intents",
        "pages": final_pages,
        "uncertainties": list(intents_obj.get("uncertainties", [])),
    }
    write_json(out_path, out_obj)

    audit_path = (
        Path(args.audit_out).expanduser().resolve()
        if args.audit_out
        else out_path.parent / "review_audit.json"
    )
    audit_obj = {
        "case_id": out_obj["case_id"],
        "review_mode": "human_review" if review_file else "auto_filter",
        "review_file": str(review_file) if review_file else None,
        "kept_operations": kept_count,
        "skipped_operations": skipped_count,
        "bbox_overrides_applied": overridden_count,
        "rows": audit_rows,
    }
    write_json(audit_path, audit_obj)

    if args.base_dir:
        upsert_stage(
            Path(args.base_dir).expanduser().resolve(),
            "review_edits",
            {
                "review_mode": audit_obj["review_mode"],
                "kept_operations": kept_count,
                "skipped_operations": skipped_count,
                "bbox_overrides_applied": overridden_count,
                "out": str(out_path),
                "audit_out": str(audit_path),
            },
        )

    print(f"Wrote final edit intents ({kept_count} ops) -> {out_path}")
    print(f"Wrote review audit -> {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
