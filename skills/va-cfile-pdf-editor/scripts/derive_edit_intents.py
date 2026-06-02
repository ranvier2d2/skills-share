#!/usr/bin/env python3
"""Derive deterministic page edit intents from raw extraction packets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    NON_ANNOTATE_ENTITY_TYPES,
    operation_order_key,
    priority_for_entity,
    read_json,
    style_for_entity,
    upsert_stage,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Derive edit intents from raw extraction.")
    parser.add_argument("--raw-extractions", required=True, help="Raw extraction directory")
    parser.add_argument("--out", required=True, help="Output edit_intents.json path")
    parser.add_argument("--case-id", default="UNKNOWN_CASE", help="Case identifier")
    parser.add_argument(
        "--auto-apply-threshold",
        type=float,
        default=0.75,
        help="Confidence threshold for automatic application",
    )
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=0.50,
        help="Lower confidence bound for requires_review items",
    )
    parser.add_argument("--base-dir", default=None, help="Optional case base directory")
    return parser.parse_args()


def short_label(entity_type: str, text: str) -> str:
    if text:
        clipped = text.strip().replace("\n", " ")
        if len(clipped) > 48:
            clipped = clipped[:45] + "..."
        return f"{entity_type}: {clipped}"
    return entity_type


def as_box(entity: dict[str, Any]) -> dict[str, int]:
    bbox = dict(entity.get("bbox", {}))
    return {
        "x": int(float(bbox.get("x", 0.0))),
        "y": int(float(bbox.get("y", 0.0))),
        "w": max(1, int(float(bbox.get("w", 1.0)))),
        "h": max(1, int(float(bbox.get("h", 1.0)))),
    }


def build_entity_ops(
    entity: dict[str, Any],
    auto_threshold: float,
    review_threshold: float,
    uncertainties: list[str],
) -> list[dict[str, Any]]:
    entity_id = str(entity.get("entity_id", "")).strip()
    entity_type = str(entity.get("entity_type", "generic_region")).strip()
    role = str(entity.get("chronology_role", "admin")).strip()
    confidence = float(entity.get("confidence", 0.0))
    text = str(entity.get("text", "")).strip()
    redaction = bool(entity.get("redaction_recommended", False))

    if not entity_id:
        uncertainties.append(f"Skipped entity without entity_id ({entity_type})")
        return []

    if confidence < review_threshold:
        uncertainties.append(
            f"{entity_id}: confidence {confidence:.2f} below {review_threshold:.2f}; no edit applied"
        )
        return []

    requires_review = confidence < auto_threshold
    style = style_for_entity(entity_type, role, redaction=redaction)
    priority = priority_for_entity(entity_type, redaction=redaction)
    bbox = as_box(entity)
    label = short_label(entity_type, text)

    ops: list[dict[str, Any]] = []

    if redaction:
        ops.append(
            {
                "op": "redact_box",
                "params": dict(bbox),
                "reason": "sensitive_entity_redaction",
                "source_entity_id": entity_id,
                "entity_type": entity_type,
                "label": label,
                "style": style,
                "priority": priority,
                "requires_review": requires_review,
                "confidence": confidence,
            }
        )
        return ops

    if entity_type in NON_ANNOTATE_ENTITY_TYPES:
        return ops

    ops.append(
        {
            "op": "draw_box",
            "params": dict(bbox),
            "reason": "entity_level_annotation",
            "source_entity_id": entity_id,
            "entity_type": entity_type,
            "label": label,
            "style": style,
            "priority": priority,
            "requires_review": requires_review,
            "confidence": confidence,
        }
    )
    ops.append(
        {
            "op": "draw_label",
            "params": {
                "x": bbox["x"],
                "y": bbox["y"] - 18,
                "text": label,
                "target_bbox": dict(bbox),
            },
            "reason": "entity_level_annotation_label",
            "source_entity_id": entity_id,
            "entity_type": entity_type,
            "label": label,
            "style": style,
            "priority": max(priority - 1, 0),
            "requires_review": requires_review,
            "confidence": confidence,
        }
    )
    return ops


def main() -> int:
    args = parse_args()
    raw_dir = Path(args.raw_extractions).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    page_files = sorted(raw_dir.glob("page_*.json"))
    if not page_files:
        raise SystemExit(f"No raw extraction page files found in {raw_dir}")

    pages = []
    uncertainties: list[str] = []
    for page_file in page_files:
        packet = read_json(page_file)
        page_id = str(packet.get("page_id", "")).strip()
        if not page_id:
            continue
        input_filename = f"{page_id}.png"
        ops: list[dict[str, Any]] = []

        for entity in list(packet.get("entities", [])):
            if not isinstance(entity, dict):
                continue
            ops.extend(
                build_entity_ops(
                    entity,
                    auto_threshold=float(args.auto_apply_threshold),
                    review_threshold=float(args.review_threshold),
                    uncertainties=uncertainties,
                )
            )
        ops = sorted(ops, key=operation_order_key)

        pages.append(
            {
                "page_id": page_id,
                "input_filename": input_filename,
                "operations": ops,
            }
        )

    intent_obj = {
        "case_id": args.case_id,
        "generated_from": "raw_extraction",
        "pages": sorted(pages, key=lambda x: str(x.get("page_id", ""))),
        "uncertainties": sorted(set(uncertainties)),
    }
    write_json(out_path, intent_obj)

    if args.base_dir:
        upsert_stage(
            Path(args.base_dir).expanduser().resolve(),
            "derive_edits",
            {
                "page_count": len(pages),
                "out": str(out_path),
                "auto_apply_threshold": float(args.auto_apply_threshold),
                "review_threshold": float(args.review_threshold),
            },
        )

    print(f"Derived edit intents for {len(pages)} page(s) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
