#!/usr/bin/env python3
"""Apply deterministic page edits from reviewed/final intent JSON."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from common import list_png_pages, operation_order_key, read_json, stable_hash_file, upsert_stage, write_json

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required for apply_page_edits.py. Install with: python3 -m pip install Pillow"
    ) from exc


STYLE_COLORS = {
    "legal": "#d42020",
    "medical": "#245dd8",
    "metadata": "#d68000",
    "redaction": "#000000",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply page edits from final edit intent JSON.")
    parser.add_argument("--pages-dir", required=True, help="Raw page PNG directory")
    parser.add_argument("--edit-intents", required=True, help="Path to edit_intents_final.json")
    parser.add_argument("--out-dir", required=True, help="Edited page output directory")
    parser.add_argument("--base-dir", default=None, help="Optional case base directory")
    return parser.parse_args()


def clamp_box(params: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    x = int(params.get("x", 0))
    y = int(params.get("y", 0))
    w = int(params.get("w", width - x))
    h = int(params.get("h", height - y))
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return x, y, w, h


def color_for_style(op: dict[str, Any], fallback: str = "metadata") -> str:
    style = str(op.get("style", fallback))
    return STYLE_COLORS.get(style, STYLE_COLORS["metadata"])


def _text_bbox(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> tuple[int, int, int, int]:
    if hasattr(draw, "textbbox"):
        return draw.textbbox((x, y), text)
    width = int(draw.textlength(text))
    return x, y, x + width, y + 12


def draw_label_with_placement(
    draw: ImageDraw.ImageDraw,
    img_width: int,
    img_height: int,
    label: str,
    color: str,
    target_bbox: tuple[int, int, int, int] | None,
    fallback_xy: tuple[int, int],
) -> None:
    pad_x = 4
    pad_y = 2

    if target_bbox is not None:
        bx, by, bw, _ = target_bbox
        preferred_x = max(0, min(bx, img_width - 10))
        preferred_y = by - 18
        t_left, t_top, t_right, t_bottom = _text_bbox(draw, preferred_x, preferred_y, label)
        text_w = t_right - t_left
        text_h = t_bottom - t_top
        preferred_x = max(0, min(preferred_x, max(0, img_width - text_w - (pad_x * 2))))

        if preferred_y >= 0:
            x = preferred_x
            y = preferred_y
        else:
            x = max(0, min(bx + 2, max(0, img_width - text_w - (pad_x * 2))))
            y = max(0, min(by + 2, max(0, img_height - text_h - (pad_y * 2))))
    else:
        x, y = fallback_xy
        x = max(0, min(x, img_width - 10))
        y = max(0, min(y, img_height - 10))
        t_left, t_top, t_right, t_bottom = _text_bbox(draw, x, y, label)
        text_w = t_right - t_left
        text_h = t_bottom - t_top
        x = max(0, min(x, max(0, img_width - text_w - (pad_x * 2))))
        y = max(0, min(y, max(0, img_height - text_h - (pad_y * 2))))

    t_left, t_top, t_right, t_bottom = _text_bbox(draw, x, y, label)
    draw.rectangle(
        [t_left - pad_x, t_top - pad_y, t_right + pad_x, t_bottom + pad_y],
        fill="white",
        outline=color,
        width=1,
    )
    draw.text((x, y), label, fill=color)


def apply_ops(img: Image.Image, operations: list[dict[str, Any]]) -> Image.Image:
    out = img.convert("RGB")
    draw = ImageDraw.Draw(out)

    for item in sorted(operations, key=operation_order_key):
        op = str(item.get("op", "")).strip()
        params = dict(item.get("params", {}))
        color = color_for_style(item)

        if op == "rotate":
            angle = float(params.get("angle", 0.0))
            out = out.rotate(angle, expand=True, fillcolor="white")
            draw = ImageDraw.Draw(out)
        elif op == "deskew":
            angle = float(params.get("angle", 0.0))
            if abs(angle) > 0.01:
                out = out.rotate(angle, expand=True, fillcolor="white")
                draw = ImageDraw.Draw(out)
        elif op == "contrast":
            factor = float(params.get("factor", 1.15))
            out = ImageEnhance.Contrast(out).enhance(factor)
            draw = ImageDraw.Draw(out)
        elif op == "denoise":
            size = int(params.get("size", 3))
            if size < 3:
                size = 3
            if size % 2 == 0:
                size += 1
            out = out.filter(ImageFilter.MedianFilter(size=size))
            draw = ImageDraw.Draw(out)
        elif op == "crop":
            x, y, w, h = clamp_box(params, out.width, out.height)
            out = out.crop((x, y, x + w, y + h))
            draw = ImageDraw.Draw(out)
        elif op == "redact_box":
            x, y, w, h = clamp_box(params, out.width, out.height)
            draw.rectangle([x, y, x + w, y + h], fill=STYLE_COLORS["redaction"])
        elif op == "draw_box":
            x, y, w, h = clamp_box(params, out.width, out.height)
            width = int(params.get("line_width", 3))
            draw.rectangle([x, y, x + w, y + h], outline=color, width=width)
        elif op == "draw_label":
            text = str(params.get("text", item.get("label", "label")))
            fallback_x = int(params.get("x", 10))
            fallback_y = int(params.get("y", 10))
            target_bbox = params.get("target_bbox")
            clamped_target = None
            if isinstance(target_bbox, dict):
                clamped_target = clamp_box(target_bbox, out.width, out.height)
            draw_label_with_placement(
                draw=draw,
                img_width=out.width,
                img_height=out.height,
                label=text,
                color=color,
                target_bbox=clamped_target,
                fallback_xy=(fallback_x, fallback_y),
            )

    return out


def main() -> int:
    args = parse_args()
    pages_dir = Path(args.pages_dir).expanduser().resolve()
    intents_path = Path(args.edit_intents).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not intents_path.exists():
        raise SystemExit(f"Edit intents not found: {intents_path}")

    intents_obj = read_json(intents_path)
    op_map = {
        str(item.get("input_filename")): sorted(list(item.get("operations", [])), key=operation_order_key)
        for item in intents_obj.get("pages", [])
        if item.get("input_filename")
    }

    manifest_rows = []
    page_files = list_png_pages(pages_dir)
    if not page_files:
        raise SystemExit(f"No PNG pages found in {pages_dir}")

    for page in page_files:
        ops = list(op_map.get(page.name, []))
        target = out_dir / page.name

        if ops:
            with Image.open(page) as img:
                edited = apply_ops(img, ops)
                edited.save(target, format="PNG")
        else:
            shutil.copy2(page, target)

        manifest_rows.append(
            {
                "page_id": target.stem,
                "filename": target.name,
                "operations_applied": ops,
                "operation_count": len(ops),
                "sha256": stable_hash_file(target),
            }
        )

    manifest = {
        "case_id": intents_obj.get("case_id", "UNKNOWN_CASE"),
        "edit_profile": "entity_level_v2",
        "page_count": len(manifest_rows),
        "pages": manifest_rows,
    }
    write_json(out_dir / "edit_manifest.json", manifest)

    if args.base_dir:
        upsert_stage(
            Path(args.base_dir).expanduser().resolve(),
            "apply_edits",
            {"page_count": len(manifest_rows), "out_dir": str(out_dir), "edit_profile": "entity_level_v2"},
        )

    print(f"Edited {len(manifest_rows)} page(s) into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
