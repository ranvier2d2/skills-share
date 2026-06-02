#!/usr/bin/env python3
"""Build chronology bundle from reconciled extraction packets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import now_iso, read_json, upsert_stage, write_json


LOW_CONFIDENCE_ENTITY_THRESHOLD = 0.50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final case bundle artifacts.")
    parser.add_argument("--case-id", required=True, help="Case identifier")
    parser.add_argument("--base-dir", required=True, help="Case base directory")
    parser.add_argument("--reconciled-dir", required=True, help="Reconciled extraction directory")
    return parser.parse_args()


def parse_iso_sort_key(date_value: Any) -> tuple[int, str]:
    if not date_value:
        return (1, "9999-99-99")
    return (0, str(date_value))


def row_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx:03d}"


def md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def make_timeline_mmd(title: str, rows: list[dict[str, Any]]) -> str:
    lines = ["timeline", f"  title \"{title}\""]
    for row in rows:
        date_s = row.get("date") or "undated"
        summary = str(row.get("summary", "")).replace('"', "'")
        lines.append(f"  {date_s} : \"{row.get('row_id')} - {summary}\"")
    return "\n".join(lines) + "\n"


def chronology_markdown(title: str, rows: list[dict[str, Any]]) -> str:
    out = [
        f"# {title}",
        "",
        "| Row ID | Date | Event Type | Event ID | Summary | Evidence Entities | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        src = f"{Path(str(row.get('source_pdf', 'unknown'))).name}:p{row.get('source_page', '?')}"
        entities = ", ".join(sorted({str(x) for x in row.get("entity_ids", []) if str(x)})) or "n/a"
        out.append(
            f"| {md_cell(row.get('row_id'))} | {md_cell(row.get('date') or 'n/a')} | "
            f"{md_cell(row.get('event_type') or 'n/a')} | {md_cell(row.get('event_id'))} | "
            f"{md_cell(row.get('summary'))} | {md_cell(entities)} | {md_cell(src)} |"
        )
    out.append("")
    return "\n".join(out)


def citations_for_rows(timeline_type: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        evidence = row.get("evidence", [])
        if evidence:
            for ev in evidence:
                out.append(
                    {
                        "row_id": row.get("row_id"),
                        "timeline_type": timeline_type,
                        "event_id": row.get("event_id"),
                        "source_pdf": row.get("source_pdf"),
                        "source_page": row.get("source_page"),
                        "quote": str(ev.get("quote", "")),
                        "bbox_id": str(ev.get("bbox_id", "missing")),
                        "entity_id": str(ev.get("entity_id", "missing")),
                    }
                )
        else:
            out.append(
                {
                    "row_id": row.get("row_id"),
                    "timeline_type": timeline_type,
                    "event_id": row.get("event_id"),
                    "source_pdf": row.get("source_pdf"),
                    "source_page": row.get("source_page"),
                    "quote": "",
                    "bbox_id": "missing",
                    "entity_id": "missing",
                }
            )
    return out


def main() -> int:
    args = parse_args()
    case_id = args.case_id
    base_dir = Path(args.base_dir).expanduser().resolve()
    reconciled_dir = Path(args.reconciled_dir).expanduser().resolve()

    pages = sorted(reconciled_dir.glob("page_*.json"))
    if not pages:
        raise SystemExit(f"No reconciled packets found in {reconciled_dir}")

    legal_rows: list[dict[str, Any]] = []
    medical_rows: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    event_type_counts: dict[str, int] = {}
    citation_rows: list[dict[str, Any]] = []
    uncertainty_rows: list[str] = []
    low_conf_entities: list[dict[str, Any]] = []

    for packet_path in pages:
        packet = read_json(packet_path)
        source_pdf = str(packet.get("source_pdf", "unknown"))
        source_page = int(packet.get("source_page", 1))
        page_id = str(packet.get("page_id", ""))

        entity_map = {
            str(entity.get("entity_id", "")): entity
            for entity in packet.get("entities", [])
            if str(entity.get("entity_id", ""))
        }

        for entity_id, entity in entity_map.items():
            confidence = float(entity.get("confidence", 0.0))
            if confidence < LOW_CONFIDENCE_ENTITY_THRESHOLD:
                low_conf_entities.append(
                    {
                        "page_id": page_id,
                        "entity_id": entity_id,
                        "entity_type": entity.get("entity_type", "unknown"),
                        "confidence": confidence,
                        "text": str(entity.get("text", "")),
                    }
                )

        for item in packet.get("uncertainties", []):
            uncertainty_rows.append(str(item))

        for event in packet.get("events", []):
            event_type = str(event.get("event_type", "admin")).strip() or "admin"
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            evidence_rows = [ev for ev in list(event.get("evidence", [])) if isinstance(ev, dict)]
            entity_ids = [str(ev.get("entity_id", "")) for ev in evidence_rows if ev.get("entity_id")]
            row = {
                "event_id": event.get("event_id"),
                "event_type": event_type,
                "date": event.get("date"),
                "summary": str(event.get("summary", "")).strip(),
                "source_pdf": source_pdf,
                "source_page": source_page,
                "evidence": evidence_rows,
                "entity_ids": entity_ids,
                "confidence": float(event.get("confidence", 0.0)),
            }
            all_rows.append(row)
            if event_type == "legal":
                legal_rows.append(row.copy())
            elif event_type == "medical":
                medical_rows.append(row.copy())

    legal_rows = sorted(legal_rows, key=lambda r: parse_iso_sort_key(r.get("date")))
    medical_rows = sorted(medical_rows, key=lambda r: parse_iso_sort_key(r.get("date")))
    all_rows = sorted(all_rows, key=lambda r: parse_iso_sort_key(r.get("date")))

    for idx, row in enumerate(legal_rows, start=1):
        row["row_id"] = row_id("L", idx)
    for idx, row in enumerate(medical_rows, start=1):
        row["row_id"] = row_id("M", idx)
    for idx, row in enumerate(all_rows, start=1):
        row["row_id"] = row_id("A", idx)

    citation_rows.extend(citations_for_rows("legal", legal_rows))
    citation_rows.extend(citations_for_rows("medical", medical_rows))
    citation_rows.extend(citations_for_rows("all", all_rows))

    chron_dir = base_dir / "chronologies"
    cit_dir = base_dir / "citations"
    qa_dir = base_dir / "qa"
    for d in (chron_dir, cit_dir, qa_dir):
        d.mkdir(parents=True, exist_ok=True)

    (chron_dir / "legal_chronology.md").write_text(
        chronology_markdown("Legal Chronology", legal_rows),
        encoding="utf-8",
    )
    (chron_dir / "medical_chronology.md").write_text(
        chronology_markdown("Medical Chronology", medical_rows),
        encoding="utf-8",
    )
    (chron_dir / "all_events_chronology.md").write_text(
        chronology_markdown("All Events Chronology", all_rows),
        encoding="utf-8",
    )

    (chron_dir / "legal_timeline.mmd").write_text(
        make_timeline_mmd("Legal Timeline", legal_rows),
        encoding="utf-8",
    )
    (chron_dir / "medical_timeline.mmd").write_text(
        make_timeline_mmd("Medical Timeline", medical_rows),
        encoding="utf-8",
    )
    (chron_dir / "all_events_timeline.mmd").write_text(
        make_timeline_mmd("All Events Timeline", all_rows),
        encoding="utf-8",
    )

    breakdown_rows = sorted(event_type_counts.items(), key=lambda x: x[0])
    breakdown_md = [
        "# Event Type Breakdown",
        "",
        "| Event Type | Count |",
        "|---|---|",
    ]
    for event_type, count in breakdown_rows:
        breakdown_md.append(f"| {md_cell(event_type)} | {count} |")
    breakdown_md.append("")
    (chron_dir / "event_type_breakdown.md").write_text("\n".join(breakdown_md), encoding="utf-8")

    citation_map = {"case_id": case_id, "citations": citation_rows}
    write_json(cit_dir / "citation_map.json", citation_map)

    missing_quote_citations = [c for c in citation_rows if not c.get("quote")]
    missing_entity_citations = [
        c for c in citation_rows if not c.get("entity_id") or c.get("entity_id") == "missing"
    ]
    qa_report = [
        "# Quality Report",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Total events: {len(all_rows)}",
        f"- Legal events: {len(legal_rows)}",
        f"- Medical events: {len(medical_rows)}",
        f"- Citation rows: {len(citation_rows)}",
        f"- Missing quote citations: {len(missing_quote_citations)}",
        f"- Missing entity-linked citations: {len(missing_entity_citations)}",
        f"- Uncertainty entries: {len(uncertainty_rows)}",
        f"- Low-confidence entities (< {LOW_CONFIDENCE_ENTITY_THRESHOLD:.2f}): {len(low_conf_entities)}",
        "",
        "## Event Types",
    ]
    if breakdown_rows:
        for event_type, count in breakdown_rows:
            qa_report.append(f"- {event_type}: {count}")
    else:
        qa_report.append("- None")

    qa_report.append("")
    qa_report.append("## Uncertainties")
    if uncertainty_rows:
        qa_report.extend([f"- {x}" for x in sorted(set(uncertainty_rows))])
    else:
        qa_report.append("- None")

    qa_report.append("")
    qa_report.append("## Unresolved Low-Confidence Entities")
    if low_conf_entities:
        for item in sorted(low_conf_entities, key=lambda x: (x["page_id"], x["entity_id"])):
            qa_report.append(
                f"- {item['page_id']} {item['entity_id']} ({item['entity_type']}) conf={item['confidence']:.2f} text='{item['text']}'"
            )
    else:
        qa_report.append("- None")

    (qa_dir / "quality_report.md").write_text("\n".join(qa_report) + "\n", encoding="utf-8")

    stage_details = {
        "case_id": case_id,
        "all_events": len(all_rows),
        "legal_events": len(legal_rows),
        "medical_events": len(medical_rows),
        "event_types": len(event_type_counts),
        "citation_rows": len(citation_rows),
        "missing_entity_citations": len(missing_entity_citations),
        "low_confidence_entities": len(low_conf_entities),
    }
    upsert_stage(base_dir, "build_bundle", stage_details)

    print(f"Built case bundle outputs under {base_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
