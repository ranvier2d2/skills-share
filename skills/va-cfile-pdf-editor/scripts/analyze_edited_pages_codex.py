#!/usr/bin/env python3
"""Normalize edited-page Codex findings into extraction JSON packets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    extract_page_id,
    list_png_pages,
    normalize_findings_payload,
    parse_page_filename,
    read_json,
    upsert_stage,
    validate_codex_findings_v2,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze edited pages and emit extraction packets.")
    parser.add_argument("--pages-dir", required=True, help="Directory containing edited page PNG files")
    parser.add_argument("--out-dir", required=True, help="Output extraction directory for edited pass")
    parser.add_argument(
        "--codex-findings",
        default=None,
        help="Optional JSON with Codex visual findings keyed by page_id",
    )
    parser.add_argument(
        "--final-intents",
        default=None,
        help="Optional edit_intents_final.json for entity binding validation",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Optional case base directory for manifest stage updates",
    )
    parser.add_argument(
        "--strict-entities",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce entity-rich findings and reject generic-only findings without explicit fallback uncertainty",
    )
    return parser.parse_args()


def load_findings(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data = read_json(Path(path).expanduser().resolve())
    return normalize_findings_payload(data)


def load_final_intent_entity_map(path: str | None) -> dict[str, set[str]]:
    if not path:
        return {}
    json_obj = read_json(Path(path).expanduser().resolve())
    mapped: dict[str, set[str]] = {}
    for page in json_obj.get("pages", []):
        page_id = str(page.get("page_id", "")).strip()
        if not page_id:
            continue
        entity_ids = {
            str(op.get("source_entity_id", "")).strip()
            for op in page.get("operations", [])
            if str(op.get("source_entity_id", "")).strip()
        }
        mapped[page_id] = entity_ids
    return mapped


def default_packet(page_id: str, source_pdf: str, source_page: int) -> dict[str, Any]:
    return {
        "page_id": page_id,
        "source_pdf": source_pdf,
        "source_page": source_page,
        "analysis_pass": "edited",
        "document_date": {"value": None, "confidence": 0.0},
        "entities": [],
        "events": [],
        "uncertainties": [
            "No Codex finding provided for this edited page. Add structured findings to codex_findings.json."
        ],
    }


def normalize_packet(base: dict[str, Any], finding: dict[str, Any]) -> dict[str, Any]:
    packet = dict(base)

    doc_date = finding.get("document_date")
    if isinstance(doc_date, dict):
        packet["document_date"] = {
            "value": doc_date.get("value"),
            "confidence": float(doc_date.get("confidence", 0.0)),
        }

    entities = finding.get("entities", [])
    packet["entities"] = [
        {
            "entity_id": str(entity.get("entity_id", "")),
            "entity_type": str(entity.get("entity_type", "generic_region")),
            "bbox": {
                "x": float(dict(entity.get("bbox", {})).get("x", 0.0)),
                "y": float(dict(entity.get("bbox", {})).get("y", 0.0)),
                "w": float(dict(entity.get("bbox", {})).get("w", 1.0)),
                "h": float(dict(entity.get("bbox", {})).get("h", 1.0)),
            },
            "text": str(entity.get("text", "")),
            "confidence": float(entity.get("confidence", 0.0)),
            "chronology_role": str(entity.get("chronology_role", "admin")),
            "redaction_recommended": bool(entity.get("redaction_recommended", False)),
        }
        for entity in entities
        if isinstance(entity, dict)
    ]

    events = finding.get("events", [])
    normalized_events = []
    for idx, event in enumerate(events, start=1):
        normalized_events.append(
            {
                "event_id": str(event.get("event_id") or f"{packet['page_id']}_event_{idx:02d}"),
                "event_type": str(event.get("event_type", "admin")),
                "summary": str(event.get("summary", "")).strip(),
                "actor": event.get("actor"),
                "date": event.get("date"),
                "date_confidence": float(event.get("date_confidence", 0.0)),
                "confidence": float(event.get("confidence", 0.0)),
                "condition_tags": list(event.get("condition_tags", [])),
                "evidence": [
                    {
                        "quote": str(ev.get("quote", "")),
                        "bbox_id": str(ev.get("bbox_id", "")),
                        "page_ref": str(ev.get("page_ref", packet["page_id"])),
                        **(
                            {"entity_id": str(ev.get("entity_id"))}
                            if ev.get("entity_id") is not None
                            else {}
                        ),
                    }
                    for ev in list(event.get("evidence", []))
                    if isinstance(ev, dict)
                ],
            }
        )
    packet["events"] = normalized_events

    packet["uncertainties"] = list(finding.get("uncertainties", []))
    return packet


def assert_event_entity_bindings(packet: dict[str, Any], allowed_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not allowed_ids:
        return errors
    page_id = str(packet.get("page_id", "unknown_page"))

    for idx, event in enumerate(packet.get("events", []), start=1):
        evidence_rows = list(event.get("evidence", []))
        if not evidence_rows:
            errors.append(f"{page_id}:event[{idx}] missing evidence for final-intent entity binding")
            continue
        has_bound_entity = False
        for ev in evidence_rows:
            entity_id = str(ev.get("entity_id", "")).strip()
            if entity_id in allowed_ids:
                has_bound_entity = True
                break
        if not has_bound_entity:
            errors.append(
                f"{page_id}:event[{idx}] has no evidence entity_id linked to final intents"
            )
    return errors


def main() -> int:
    args = parse_args()
    pages_dir = Path(args.pages_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    findings = load_findings(args.codex_findings)
    if findings:
        validation_errors = validate_codex_findings_v2(findings, strict_entities=args.strict_entities)
        if validation_errors:
            for err in validation_errors:
                print(f"ERROR: {err}")
            raise SystemExit("codex_findings failed v2 validation")

    final_intent_entities = load_final_intent_entity_map(args.final_intents)
    page_files = list_png_pages(pages_dir)
    if not page_files:
        raise SystemExit(f"No PNG pages found in {pages_dir}")

    render_manifest_path = pages_dir.parent / "raw" / "render_manifest.json"
    source_map = {}
    if render_manifest_path.exists():
        render_manifest = read_json(render_manifest_path)
        for item in render_manifest.get("pages", []):
            source_map[item.get("page_id")] = item

    written = 0
    for page in page_files:
        page_id = extract_page_id(page.name)
        _, inferred_page = parse_page_filename(page.name)
        source_meta = source_map.get(page_id, {})
        source_pdf = str(source_meta.get("source_pdf", "unknown"))
        source_page = int(source_meta.get("source_page", inferred_page))

        packet = default_packet(page_id, source_pdf, source_page)
        finding = findings.get(page_id, {})
        if isinstance(finding, dict) and finding:
            packet = normalize_packet(packet, finding)

        if page_id in final_intent_entities:
            link_errors = assert_event_entity_bindings(packet, final_intent_entities[page_id])
            if link_errors:
                for err in link_errors:
                    print(f"ERROR: {err}")
                raise SystemExit("Edited-pass event evidence failed final-intent entity binding checks")

        write_json(out_dir / f"page_{page_id}.json", packet)
        written += 1

    index_obj = {
        "analysis_pass": "edited",
        "page_count": written,
        "pages_dir": str(pages_dir),
        "codex_findings": str(args.codex_findings) if args.codex_findings else None,
        "strict_entities": bool(args.strict_entities),
        "final_intents": str(args.final_intents) if args.final_intents else None,
    }
    write_json(out_dir / "index.json", index_obj)

    if args.base_dir:
        upsert_stage(
            Path(args.base_dir).expanduser().resolve(),
            "analyze_edited",
            {
                "page_count": written,
                "out_dir": str(out_dir),
                "strict_entities": bool(args.strict_entities),
                "final_intents": str(args.final_intents) if args.final_intents else None,
            },
        )

    print(f"Wrote {written} edited extraction packet(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
