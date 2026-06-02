#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


NOTE_BG = "#FEF08A"
NOTE_BORDER = "#FACC15"
NOTE_TEXT = "#422006"
ARROW = "#F97316"
ARROW_LABEL_BG = "#FFF7ED"
ARROW_LABEL_BORDER = "#FDBA74"

PADDING_X = 10
PADDING_Y = 8
LINE_SPACING = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render notes and arrows onto a PNG screenshot.")
    parser.add_argument("input_image", type=Path, help="Source image path")
    parser.add_argument("spec_json", type=Path, help="Annotation spec JSON path")
    parser.add_argument("output_image", type=Path, help="Output image path")
    return parser.parse_args()


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.strip().split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_note(draw: ImageDraw.ImageDraw, note: dict, font_title: ImageFont.ImageFont, font_body: ImageFont.ImageFont) -> None:
    x = int(note["x"])
    y = int(note["y"])
    width = int(note.get("width", 220))
    text = str(note["text"])
    body_width = max(width - (PADDING_X * 2), 80)
    lines = wrap_lines(draw, text, font_body, body_width)

    title_box = draw.textbbox((0, 0), "NOTE", font=font_title)
    body_boxes = [draw.textbbox((0, 0), line, font=font_body) for line in lines]
    line_height = max((box[3] - box[1] for box in body_boxes), default=14)
    body_height = len(lines) * line_height + max(0, len(lines) - 1) * LINE_SPACING
    title_height = title_box[3] - title_box[1]
    header_h = title_height + (PADDING_Y * 2)
    total_h = header_h + body_height + (PADDING_Y * 2)

    draw.rounded_rectangle((x, y, x + width, y + total_h), radius=6, fill=NOTE_BG, outline=NOTE_BORDER, width=2)
    draw.rectangle((x, y, x + width, y + header_h), fill="#FDE68A")
    draw.line((x, y + header_h, x + width, y + header_h), fill="#EAB308", width=1)
    draw.text((x + PADDING_X, y + PADDING_Y), "NOTE", fill=NOTE_TEXT, font=font_title)

    cursor_y = y + header_h + PADDING_Y
    for line in lines:
        draw.text((x + PADDING_X, cursor_y), line, fill=NOTE_TEXT, font=font_body)
        box = draw.textbbox((0, 0), line, font=font_body)
        cursor_y += (box[3] - box[1]) + LINE_SPACING


def arrow_head_points(x1: float, y1: float, x2: float, y2: float, length: float = 16, half_width: float = 7) -> list[tuple[float, float]]:
    angle = math.atan2(y2 - y1, x2 - x1)
    tip = (x2, y2)
    left = (
        x2 - length * math.cos(angle) + half_width * math.sin(angle),
        y2 - length * math.sin(angle) - half_width * math.cos(angle),
    )
    right = (
        x2 - length * math.cos(angle) - half_width * math.sin(angle),
        y2 - length * math.sin(angle) + half_width * math.cos(angle),
    )
    return [tip, left, right]


def draw_arrow(draw: ImageDraw.ImageDraw, arrow: dict, font_label: ImageFont.ImageFont) -> None:
    x1 = float(arrow["x1"])
    y1 = float(arrow["y1"])
    x2 = float(arrow["x2"])
    y2 = float(arrow["y2"])
    draw.line((x1, y1, x2, y2), fill=ARROW, width=4)
    draw.polygon(arrow_head_points(x1, y1, x2, y2), fill=ARROW)

    label = str(arrow.get("label", "")).strip()
    if not label:
        return

    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    box = draw.textbbox((0, 0), label, font=font_label)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    left = mx + 10
    top = my - th - 10
    draw.rounded_rectangle(
        (left - 6, top - 4, left + tw + 6, top + th + 4),
        radius=5,
        fill=ARROW_LABEL_BG,
        outline=ARROW_LABEL_BORDER,
        width=1,
    )
    draw.text((left, top), label, fill="#7C2D12", font=font_label)


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise ValueError("Spec must be a JSON object.")
    for key in ("notes", "arrows"):
        value = spec.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"Spec field '{key}' must be a list.")


def main() -> None:
    args = parse_args()
    spec = json.loads(args.spec_json.read_text())
    validate_spec(spec)

    image = Image.open(args.input_image).convert("RGBA")
    draw = ImageDraw.Draw(image)
    font_title = load_font(12)
    font_body = load_font(14)
    font_label = load_font(13)

    for arrow in spec.get("arrows", []):
        draw_arrow(draw, arrow, font_label)
    for note in spec.get("notes", []):
        draw_note(draw, note, font_title, font_body)

    args.output_image.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output_image)


if __name__ == "__main__":
    main()
