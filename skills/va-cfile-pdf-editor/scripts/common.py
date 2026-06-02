#!/usr/bin/env python3
"""Shared helpers for va-cfile-pdf-editor scripts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PAGE_RE = re.compile(r"^(doc\d+)_page(\d{4})\.png$")
GENERIC_ENTITY_TYPES = {
    "header_region",
    "primary_evidence_region",
    "generic_region",
    "section_region",
}
# Generic region entities are fallback-only and are not drawn/labeled by default.
NON_ANNOTATE_ENTITY_TYPES = set(GENERIC_ENTITY_TYPES)
PII_ENTITY_TYPES = {"ssn", "dob", "address", "phone", "email"}
LEGAL_ENTITY_TYPES = {"claim_number", "decision_date", "invoice_number"}
MEDICAL_ENTITY_TYPES = {"diagnosis", "imaging_result"}
METADATA_ENTITY_TYPES = {
    "invoice_date",
    "due_date",
    "service_date",
    "total_amount",
    "veteran_name",
    "provider_name",
}
def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stable_hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def list_png_pages(pages_dir: Path) -> list[Path]:
    files = [p for p in pages_dir.glob("*.png") if p.is_file()]
    return sorted(files, key=lambda p: p.name)


def parse_page_filename(filename: str) -> tuple[str, int]:
    match = PAGE_RE.match(filename)
    if not match:
        raise ValueError(f"Invalid page filename '{filename}'. Expected docNN_pageMMMM.png")
    doc_id = match.group(1)
    page_no = int(match.group(2))
    return doc_id, page_no


def extract_page_id(filename: str) -> str:
    stem = Path(filename).stem
    if "_page" not in stem:
        raise ValueError(f"Cannot extract page_id from '{filename}'")
    return stem


def normalize_event_key(event: dict[str, Any]) -> str:
    event_id = str(event.get("event_id", "")).strip().lower()
    if event_id:
        return f"id::{event_id}"
    summary = str(event.get("summary", "")).strip().lower()
    date_s = str(event.get("date", "")).strip().lower()
    return f"fallback::{summary}::{date_s}"


def normalize_entity_key(entity: dict[str, Any]) -> str:
    entity_id = str(entity.get("entity_id", "")).strip().lower()
    if entity_id:
        return f"id::{entity_id}"
    entity_type = str(entity.get("entity_type", "")).strip().lower()
    text = str(entity.get("text", "")).strip().lower()
    return f"fallback::{entity_type}::{text}"


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pipeline_stage_file(base_dir: Path) -> Path:
    return base_dir / "manifest.json"


def read_manifest(base_dir: Path) -> dict[str, Any]:
    path = pipeline_stage_file(base_dir)
    if path.exists():
        return read_json(path)
    return {"stages": []}


def upsert_stage(base_dir: Path, stage_name: str, details: dict[str, Any]) -> None:
    manifest = read_manifest(base_dir)
    stages = [s for s in manifest.get("stages", []) if s.get("name") != stage_name]
    stages.append({"name": stage_name, "completed_at": now_iso(), "details": details})
    manifest["stages"] = stages
    write_json(pipeline_stage_file(base_dir), manifest)


def stage_order_ok(stages: list[dict[str, Any]], ordered_names: list[str]) -> bool:
    index_map = {name: i for i, name in enumerate(ordered_names)}
    seen = []
    for stage in stages:
        name = stage.get("name")
        if name in index_map:
            seen.append(index_map[name])
    return seen == sorted(seen)


def has_write_access(path: Path) -> bool:
    target = path if path.exists() else path.parent
    return os.access(target, os.W_OK)


def normalize_findings_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        mapped: dict[str, Any] = {}
        for item in data:
            if isinstance(item, dict) and item.get("page_id"):
                mapped[str(item["page_id"])] = item
        return mapped
    if isinstance(data, dict):
        return data
    return {}


def is_generic_only_entities(entities: list[dict[str, Any]]) -> bool:
    if not entities:
        return False
    types = {str(e.get("entity_type", "")) for e in entities}
    if not types:
        return False
    return types.issubset(GENERIC_ENTITY_TYPES)


def has_specific_entities(entities: list[dict[str, Any]]) -> bool:
    return any(str(e.get("entity_type", "")) not in GENERIC_ENTITY_TYPES for e in entities)


def _validate_bbox(bbox: dict[str, Any], page_id: str, errors: list[str]) -> None:
    needed = ("x", "y", "w", "h")
    for key in needed:
        if key not in bbox:
            errors.append(f"{page_id}: bbox missing '{key}'")
            return
    for key in needed:
        value = bbox.get(key)
        if not isinstance(value, (int, float)):
            errors.append(f"{page_id}: bbox '{key}' must be number")
            return
    if bbox["w"] <= 0 or bbox["h"] <= 0:
        errors.append(f"{page_id}: bbox width/height must be > 0")


def validate_codex_findings_v2(
    findings: dict[str, Any],
    strict_entities: bool = True,
    allow_generic_fallback: bool = True,
) -> list[str]:
    errors: list[str] = []

    if not isinstance(findings, dict):
        return ["codex findings must be a dictionary keyed by page_id"]

    for page_key, payload in findings.items():
        page_id = str(page_key)
        if not isinstance(payload, dict):
            errors.append(f"{page_id}: payload must be object")
            continue

        for required in ("page_id", "entities", "events", "uncertainties"):
            if required not in payload:
                errors.append(f"{page_id}: missing required field '{required}'")

        if payload.get("page_id") != page_id:
            errors.append(f"{page_id}: payload.page_id must match key")

        entities = payload.get("entities", [])
        if not isinstance(entities, list):
            errors.append(f"{page_id}: entities must be array")
            entities = []

        seen_entity_ids: set[str] = set()
        for idx, entity in enumerate(entities, start=1):
            prefix = f"{page_id}:entity[{idx}]"
            if not isinstance(entity, dict):
                errors.append(f"{prefix} must be object")
                continue
            for req in (
                "entity_id",
                "entity_type",
                "bbox",
                "text",
                "confidence",
                "chronology_role",
                "redaction_recommended",
            ):
                if req not in entity:
                    errors.append(f"{prefix} missing '{req}'")
            if "bbox" in entity and isinstance(entity.get("bbox"), dict):
                _validate_bbox(entity["bbox"], page_id, errors)
            conf = entity.get("confidence")
            if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
                errors.append(f"{prefix} confidence must be 0..1")
            if not isinstance(entity.get("redaction_recommended"), bool):
                errors.append(f"{prefix} redaction_recommended must be bool")
            role = str(entity.get("chronology_role", ""))
            if not role.strip():
                errors.append(f"{prefix} chronology_role must be non-empty")
            entity_id = str(entity.get("entity_id", "")).strip()
            if not entity_id:
                errors.append(f"{prefix} entity_id must be non-empty")
            elif entity_id in seen_entity_ids:
                errors.append(f"{page_id}: duplicate entity_id '{entity_id}'")
            else:
                seen_entity_ids.add(entity_id)

        if strict_entities and entities:
            if is_generic_only_entities(entities):
                uncertainties = payload.get("uncertainties", [])
                has_fallback_flag = any(
                    "no specific entities" in str(x).lower() for x in uncertainties
                )
                if not (allow_generic_fallback and has_fallback_flag):
                    errors.append(
                        f"{page_id}: generic-only entities provided without explicit fallback uncertainty"
                    )

        events = payload.get("events", [])
        if not isinstance(events, list):
            errors.append(f"{page_id}: events must be array")
            continue

        entity_ids = {str(e.get("entity_id")) for e in entities if isinstance(e, dict)}
        for idx, event in enumerate(events, start=1):
            prefix = f"{page_id}:event[{idx}]"
            if not isinstance(event, dict):
                errors.append(f"{prefix} must be object")
                continue
            for req in (
                "event_id",
                "event_type",
                "summary",
                "date",
                "date_confidence",
                "confidence",
                "condition_tags",
                "evidence",
            ):
                if req not in event:
                    errors.append(f"{prefix} missing '{req}'")
            event_type = str(event.get("event_type", ""))
            if not event_type.strip():
                errors.append(f"{prefix} event_type must be non-empty")
            evidence = event.get("evidence", [])
            if isinstance(evidence, list):
                for e_idx, ev in enumerate(evidence, start=1):
                    if not isinstance(ev, dict):
                        errors.append(f"{prefix}:evidence[{e_idx}] must be object")
                        continue
                    for req in ("quote", "bbox_id", "page_ref"):
                        if req not in ev:
                            errors.append(f"{prefix}:evidence[{e_idx}] missing '{req}'")
                    if "entity_id" in ev and ev.get("entity_id") not in entity_ids and entity_ids:
                        errors.append(
                            f"{prefix}:evidence[{e_idx}] entity_id not declared in entities"
                        )

        uncertainties = payload.get("uncertainties")
        if not isinstance(uncertainties, list):
            errors.append(f"{page_id}: uncertainties must be array")

    return errors


def style_for_entity(entity_type: str, chronology_role: str, redaction: bool = False) -> str:
    if redaction or entity_type in PII_ENTITY_TYPES:
        return "redaction"
    if chronology_role == "legal" or entity_type in LEGAL_ENTITY_TYPES:
        return "legal"
    if chronology_role == "medical" or entity_type in MEDICAL_ENTITY_TYPES:
        return "medical"
    if entity_type in METADATA_ENTITY_TYPES:
        return "metadata"
    return "metadata"


def priority_for_entity(entity_type: str, redaction: bool = False) -> int:
    if redaction:
        return 95
    if entity_type in {"decision_date", "diagnosis", "claim_number"}:
        return 90
    if entity_type in {"invoice_number", "due_date", "service_date", "imaging_result"}:
        return 85
    if entity_type in {"invoice_date", "total_amount"}:
        return 80
    return 70


def operation_order_key(operation: dict[str, Any]) -> tuple[int, int, str, str]:
    op_order = {
        "crop": 10,
        "rotate": 20,
        "deskew": 30,
        "contrast": 40,
        "denoise": 50,
        "redact_box": 60,
        "draw_box": 70,
        "draw_label": 80,
    }
    priority = int(operation.get("priority", 0))
    op = str(operation.get("op", ""))
    entity_id = str(operation.get("source_entity_id", ""))
    return (-priority, op_order.get(op, 999), entity_id, op)


def validate_annotation_review(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "case_id",
        "reviewed_by",
        "approved_entities",
        "rejected_entities",
        "bbox_overrides",
        "notes",
    )
    for key in required:
        if key not in review:
            errors.append(f"annotation_review missing '{key}'")
    if not isinstance(review.get("approved_entities", []), list):
        errors.append("annotation_review.approved_entities must be array")
    if not isinstance(review.get("rejected_entities", []), list):
        errors.append("annotation_review.rejected_entities must be array")
    overrides = review.get("bbox_overrides", [])
    if not isinstance(overrides, list):
        errors.append("annotation_review.bbox_overrides must be array")
    else:
        for idx, item in enumerate(overrides, start=1):
            if not isinstance(item, dict):
                errors.append(f"annotation_review.bbox_overrides[{idx}] must be object")
                continue
            if "entity_id" not in item:
                errors.append(f"annotation_review.bbox_overrides[{idx}] missing entity_id")
            bbox = item.get("bbox")
            if not isinstance(bbox, dict):
                errors.append(f"annotation_review.bbox_overrides[{idx}] missing bbox object")
                continue
            _validate_bbox(bbox, f"annotation_review[{idx}]", errors)
    if not isinstance(review.get("notes", []), list):
        errors.append("annotation_review.notes must be array")
    return errors
