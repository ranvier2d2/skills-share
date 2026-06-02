#!/usr/bin/env python3
"""Reconcile raw and edited extraction packets into canonical events/entities."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    coerce_float,
    normalize_entity_key,
    normalize_event_key,
    read_json,
    upsert_stage,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile raw and edited extraction packets.")
    parser.add_argument("--raw-dir", required=True, help="Raw extraction directory")
    parser.add_argument("--edited-dir", required=True, help="Edited extraction directory")
    parser.add_argument("--out-dir", required=True, help="Output reconciled extraction directory")
    parser.add_argument("--base-dir", default=None, help="Optional case base directory")
    return parser.parse_args()


def index_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in events:
        out[normalize_event_key(event)] = event
    return out


def index_entities(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entity in entities:
        out[normalize_entity_key(entity)] = entity
    return out


def pick_event(
    raw_event: dict[str, Any] | None,
    edited_event: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str, str | None]:
    if raw_event is None and edited_event is None:
        return None, "none", "Missing both raw and edited event"
    if raw_event is None:
        chosen = dict(edited_event)
        chosen["selected_from"] = "edited"
        return chosen, "improved", None
    if edited_event is None:
        chosen = dict(raw_event)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", None

    raw_conf = coerce_float(raw_event.get("confidence"), 0.0)
    edited_conf = coerce_float(edited_event.get("confidence"), 0.0)
    raw_ev = list(raw_event.get("evidence", []))
    edited_ev = list(edited_event.get("evidence", []))

    if edited_conf > raw_conf and edited_ev:
        chosen = dict(edited_event)
        chosen["selected_from"] = "edited"
        return chosen, "improved", None

    if (edited_conf < raw_conf and not edited_ev) or (not edited_ev and raw_ev):
        chosen = dict(raw_event)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", "Edited pass lost evidence or confidence"

    if abs(edited_conf - raw_conf) <= 0.05:
        chosen = dict(raw_event)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", "Confidence conflict unresolved; retained raw event"

    chosen = dict(raw_event)
    chosen["selected_from"] = "raw"
    return chosen, "preserved", None


def pick_entity(
    raw_entity: dict[str, Any] | None,
    edited_entity: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str, str | None]:
    if raw_entity is None and edited_entity is None:
        return None, "none", "Missing both raw and edited entity"
    if raw_entity is None:
        chosen = dict(edited_entity)
        chosen["selected_from"] = "edited"
        return chosen, "improved", None
    if edited_entity is None:
        chosen = dict(raw_entity)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", None

    raw_conf = coerce_float(raw_entity.get("confidence"), 0.0)
    edited_conf = coerce_float(edited_entity.get("confidence"), 0.0)

    if edited_conf > raw_conf:
        chosen = dict(edited_entity)
        chosen["selected_from"] = "edited"
        return chosen, "improved", None

    if edited_conf < raw_conf:
        chosen = dict(raw_entity)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", None

    raw_bbox = dict(raw_entity.get("bbox", {}))
    edited_bbox = dict(edited_entity.get("bbox", {}))
    if raw_bbox != edited_bbox:
        chosen = dict(raw_entity)
        chosen["selected_from"] = "raw"
        return chosen, "preserved", "Entity bbox conflict unresolved; retained raw entity"

    chosen = dict(raw_entity)
    chosen["selected_from"] = "raw"
    return chosen, "preserved", None


def normalize_event_evidence(
    page_id: str,
    event: dict[str, Any],
    valid_entity_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    warnings: list[str] = []

    for idx, ev in enumerate(list(event.get("evidence", [])), start=1):
        if not isinstance(ev, dict):
            warnings.append(f"{page_id}:{event.get('event_id')} evidence[{idx}] is not an object")
            continue
        entity_id = str(ev.get("entity_id", "")).strip()
        if not entity_id:
            bbox_id = str(ev.get("bbox_id", "")).strip()
            if bbox_id in valid_entity_ids:
                entity_id = bbox_id
        if not entity_id or entity_id not in valid_entity_ids:
            warnings.append(
                f"{page_id}:{event.get('event_id')} evidence[{idx}] missing valid entity_id"
            )
            entity_id = "missing"

        out.append(
            {
                "quote": str(ev.get("quote", "")),
                "bbox_id": str(ev.get("bbox_id", "")),
                "page_ref": str(ev.get("page_ref", page_id)),
                "entity_id": entity_id,
            }
        )

    return out, warnings


def main() -> int:
    args = parse_args()
    raw_dir = Path(args.raw_dir).expanduser().resolve()
    edited_dir = Path(args.edited_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_pages = sorted(raw_dir.glob("page_*.json"))
    if not raw_pages:
        raise SystemExit(f"No raw page packets found in {raw_dir}")

    improved_events = 0
    preserved_events = 0
    unresolved_event_conflicts = 0
    improved_entities = 0
    preserved_entities = 0
    unresolved_entity_conflicts = 0
    processed = 0

    for raw_path in raw_pages:
        raw_packet = read_json(raw_path)
        page_id = str(raw_packet.get("page_id", ""))
        edited_path = edited_dir / raw_path.name
        edited_packet = read_json(edited_path) if edited_path.exists() else {}

        raw_events = index_events(list(raw_packet.get("events", [])))
        edited_events = index_events(list(edited_packet.get("events", [])))
        raw_entities = index_entities(list(raw_packet.get("entities", [])))
        edited_entities = index_entities(list(edited_packet.get("entities", [])))

        all_event_keys = sorted(set(raw_events) | set(edited_events))
        all_entity_keys = sorted(set(raw_entities) | set(edited_entities))

        reconciled_entities = []
        uncertainties = list(raw_packet.get("uncertainties", []))
        uncertainties.extend(list(edited_packet.get("uncertainties", [])))

        for key in all_entity_keys:
            picked, state, conflict_note = pick_entity(raw_entities.get(key), edited_entities.get(key))
            if picked is None:
                continue
            reconciled_entities.append(picked)
            if state == "improved":
                improved_entities += 1
            else:
                preserved_entities += 1
            if conflict_note:
                unresolved_entity_conflicts += 1
                uncertainties.append(f"{page_id}: {conflict_note}")

        valid_entity_ids = {
            str(entity.get("entity_id", "")).strip()
            for entity in reconciled_entities
            if str(entity.get("entity_id", "")).strip()
        }

        reconciled_events = []
        for key in all_event_keys:
            picked, state, conflict_note = pick_event(raw_events.get(key), edited_events.get(key))
            if picked is None:
                continue
            normalized_evidence, evidence_warnings = normalize_event_evidence(page_id, picked, valid_entity_ids)
            picked["evidence"] = normalized_evidence
            reconciled_events.append(picked)

            if state == "improved":
                improved_events += 1
            else:
                preserved_events += 1
            if conflict_note:
                unresolved_event_conflicts += 1
                uncertainties.append(f"{page_id}: {conflict_note}")
            uncertainties.extend(evidence_warnings)

        reconciled_packet = {
            "page_id": page_id,
            "source_pdf": raw_packet.get("source_pdf", "unknown"),
            "source_page": int(raw_packet.get("source_page", 1)),
            "analysis_pass": "reconciled",
            "entities": reconciled_entities,
            "events": reconciled_events,
            "uncertainties": sorted(set(str(x) for x in uncertainties)),
        }

        write_json(out_dir / raw_path.name, reconciled_packet)
        processed += 1

    report = {
        "pages_processed": processed,
        "events_improved_from_edited": improved_events,
        "events_preserved_from_raw": preserved_events,
        "conflicts_unresolved": unresolved_event_conflicts,
        "entities_improved_from_edited": improved_entities,
        "entities_preserved_from_raw": preserved_entities,
        "entity_conflicts_unresolved": unresolved_entity_conflicts,
        "strategy": "two_pass_reconcile",
        "rules": [
            "Prefer edited-pass values when confidence improves and evidence is retained",
            "Preserve raw-pass values when edited-pass loses confidence or evidence",
            "Keep unresolved conflicts as explicit uncertainty entries",
        ],
    }
    write_json(out_dir / "reconciliation_report.json", report)

    if args.base_dir:
        upsert_stage(
            Path(args.base_dir).expanduser().resolve(),
            "reconcile",
            {
                "pages_processed": processed,
                "improved_events": improved_events,
                "preserved_events": preserved_events,
                "event_conflicts": unresolved_event_conflicts,
                "improved_entities": improved_entities,
                "preserved_entities": preserved_entities,
                "entity_conflicts": unresolved_entity_conflicts,
                "out_dir": str(out_dir),
            },
        )

    print(f"Reconciled {processed} page packet(s) into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
