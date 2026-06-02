#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


MARGIN = 12
DEFAULT_WIDTH = 220
DEFAULT_GAP = 48


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve live anchor callouts into pixel note/arrow specs.")
    parser.add_argument("screenshot", type=Path, help="Screenshot image used for bounds")
    parser.add_argument("detections_json", type=Path, help="Detections JSON exported from the live page")
    parser.add_argument("anchor_spec_json", type=Path, help="Anchor-based callout spec JSON")
    parser.add_argument("pixel_spec_json", type=Path, help="Resolved pixel spec output path")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text())


def normalize(value) -> str:
    return str(value or "").strip().lower()


def estimate_note_height(text: str, width: int) -> int:
    chars_per_line = max(12, int((width - 20) / 8))
    words = text.split()
    if not words:
        return 78
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if len(trial) <= chars_per_line:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return 44 + len(lines) * 22


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_detection(detection: dict, anchor: dict) -> int:
    score = 0
    kind = anchor.get("kind")
    if kind:
        if normalize(detection.get("kind")) != normalize(kind):
            return -1
        score += 100

    anchor_id = anchor.get("id")
    if anchor_id:
        if detection.get("id") != anchor_id:
            return -1
        score += 200

    meta = detection.get("meta", {})
    label = normalize(detection.get("label"))
    text = normalize(meta.get("text"))

    text_contains = anchor.get("text_contains")
    if text_contains:
        needle = normalize(text_contains)
        if needle in text:
            score += 60
        elif needle in label:
            score += 40
        else:
            return -1

    label_contains = anchor.get("label_contains")
    if label_contains:
        needle = normalize(label_contains)
        if needle in label:
            score += 40
        else:
            return -1

    role = anchor.get("role")
    if role:
        if normalize(meta.get("role")) != normalize(role):
            return -1
        score += 20

    tag = anchor.get("tag")
    if tag:
        if normalize(meta.get("tag")) != normalize(tag):
            return -1
        score += 20

    return score


def normalize_detections_payload(payload, image_w: int, image_h: int) -> list[dict]:
    if isinstance(payload, list):
        detections = payload
        viewport = {}
    elif isinstance(payload, dict):
        detections = payload.get("detections", [])
        viewport = payload.get("viewport", {}) or {}
    else:
        raise ValueError("Detections JSON must be an array or an object with a 'detections' array.")

    if not isinstance(detections, list):
        raise ValueError("Detections payload must contain a detections list.")

    scroll_x = float(viewport.get("scrollX", 0))
    scroll_y = float(viewport.get("scrollY", 0))
    viewport_w = float(viewport.get("width", 0)) or float(image_w)
    viewport_h = float(viewport.get("height", 0)) or float(image_h)
    scale_x = image_w / viewport_w if viewport_w else 1.0
    scale_y = image_h / viewport_h if viewport_h else 1.0

    normalized = []
    for detection in detections:
        rect = detection.get("rect")
        if not isinstance(rect, dict):
            continue
        x = (float(rect["x"]) - scroll_x) * scale_x
        y = (float(rect["y"]) - scroll_y) * scale_y
        w = float(rect["w"]) * scale_x
        h = float(rect["h"]) * scale_y
        normalized.append({
            **detection,
            "rect": {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "cx": x + (w / 2),
                "cy": y + (h / 2)
            }
        })
    return normalized


def resolve_detection(detections: list[dict], anchor: dict) -> dict:
    scored = []
    for detection in detections:
        score = score_detection(detection, anchor)
        if score >= 0:
            scored.append((score, detection))
    if not scored:
        raise ValueError(f"No detection matched anchor: {anchor}")
    scored.sort(key=lambda item: (-item[0], item[1].get("id", "")))
    return scored[0][1]


def point_on_target(rect: dict, placement: str) -> tuple[float, float]:
    if placement == "left":
        return rect["x"], rect["cy"]
    if placement == "right":
        return rect["x"] + rect["w"], rect["cy"]
    if placement == "top":
        return rect["cx"], rect["y"]
    return rect["cx"], rect["y"] + rect["h"]


def note_position(rect: dict, placement: str, width: int, height: int, gap: int, dx: int, dy: int, image_w: int, image_h: int) -> tuple[float, float]:
    if placement == "left":
        x = rect["x"] - gap - width
        y = rect["cy"] - (height / 2)
    elif placement == "right":
        x = rect["x"] + rect["w"] + gap
        y = rect["cy"] - (height / 2)
    elif placement == "top":
        x = rect["cx"] - (width / 2)
        y = rect["y"] - gap - height
    else:
        x = rect["cx"] - (width / 2)
        y = rect["y"] + rect["h"] + gap

    x += dx
    y += dy

    x = clamp(x, MARGIN, image_w - width - MARGIN)
    y = clamp(y, MARGIN, image_h - height - MARGIN)
    return x, y


def note_arrow_start(note_x: float, note_y: float, note_w: int, note_h: int, placement: str) -> tuple[float, float]:
    if placement == "left":
        return note_x + note_w, note_y + (note_h / 2)
    if placement == "right":
        return note_x, note_y + (note_h / 2)
    if placement == "top":
        return note_x + (note_w / 2), note_y + note_h
    return note_x + (note_w / 2), note_y


def validate_anchor_spec(spec: dict) -> list[dict]:
    if not isinstance(spec, dict):
        raise ValueError("Anchor spec must be a JSON object.")
    callouts = spec.get("callouts")
    if not isinstance(callouts, list):
        raise ValueError("Anchor spec must contain a 'callouts' list.")
    return callouts


def main() -> None:
    args = parse_args()
    anchor_spec = load_json(args.anchor_spec_json)
    callouts = validate_anchor_spec(anchor_spec)

    with Image.open(args.screenshot) as image:
        image_w, image_h = image.size

    detections = normalize_detections_payload(load_json(args.detections_json), image_w, image_h)

    notes = []
    arrows = []

    for callout in callouts:
        anchor = callout.get("anchor")
        text = str(callout.get("text", "")).strip()
        if not isinstance(anchor, dict):
          raise ValueError(f"Callout is missing an anchor object: {callout}")
        if not text:
          raise ValueError(f"Callout is missing note text: {callout}")

        detection = resolve_detection(detections, anchor)
        rect = detection["rect"]
        placement = str(callout.get("placement", "right")).lower()
        if placement not in {"left", "right", "top", "bottom"}:
            raise ValueError(f"Unsupported placement '{placement}' in callout: {callout}")

        width = int(callout.get("width", DEFAULT_WIDTH))
        gap = int(callout.get("gap", DEFAULT_GAP))
        dx = int(callout.get("dx", 0))
        dy = int(callout.get("dy", 0))
        height = estimate_note_height(text, width)
        x, y = note_position(rect, placement, width, height, gap, dx, dy, image_w, image_h)
        start_x, start_y = note_arrow_start(x, y, width, height, placement)
        end_x, end_y = point_on_target(rect, placement)

        notes.append({
            "x": round(x),
            "y": round(y),
            "width": width,
            "text": text
        })
        arrows.append({
            "x1": round(start_x),
            "y1": round(start_y),
            "x2": round(end_x),
            "y2": round(end_y),
            "label": callout.get("label", "")
        })

    output = {
        "notes": notes,
        "arrows": arrows
    }
    args.pixel_spec_json.parent.mkdir(parents=True, exist_ok=True)
    args.pixel_spec_json.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
