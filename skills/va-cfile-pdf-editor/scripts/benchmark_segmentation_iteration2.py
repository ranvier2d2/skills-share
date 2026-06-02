#!/usr/bin/env python3
"""Iteration 2 benchmark harness for segmentation-assisted document parsing research.

This script does not mutate the existing v1 pipeline. It evaluates a baseline native-text
block detector against optional segmentation-assisted variants and emits reproducible metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

from PIL import Image

try:
    import pdfplumber
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "pdfplumber is required for baseline native-text benchmarking. "
        "Install with: python3 -m pip install pdfplumber"
    ) from exc


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config_path_value(value: Any) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark segmentation-assisted parsing (Iteration 2).")
    parser.add_argument("--config", required=True, help="Path to JSON benchmark config")
    parser.add_argument("--out", default=None, help="Optional output metrics JSON path override")
    parser.add_argument("--print-summary", action="store_true", help="Print compact summary")
    return parser.parse_args()


def load_ground_truth(path: Path) -> dict[str, list[dict[str, Any]]]:
    obj = read_json(path)
    pages = obj.get("pages", {}) if isinstance(obj, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}

    if isinstance(pages, dict):
        for page_id, payload in pages.items():
            blocks = payload.get("blocks", []) if isinstance(payload, dict) else []
            normalized: list[dict[str, Any]] = []
            for idx, block in enumerate(blocks, start=1):
                if not isinstance(block, dict):
                    continue
                bbox = dict(block.get("bbox", {}))
                if not all(k in bbox for k in ("x", "y", "w", "h")):
                    continue
                normalized.append(
                    {
                        "id": str(block.get("id", f"{page_id}_gt_{idx:03d}")),
                        "bbox": {
                            "x": float(bbox["x"]),
                            "y": float(bbox["y"]),
                            "w": float(bbox["w"]),
                            "h": float(bbox["h"]),
                        },
                        "order": int(block.get("order", idx)),
                    }
                )
            out[str(page_id)] = normalized
    return out


def box_iou(a: dict[str, float], b: dict[str, float]) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0

    union = (a["w"] * a["h"]) + (b["w"] * b["h"]) - inter
    if union <= 0.0:
        return 0.0
    return inter / union


def greedy_matches(
    preds: list[dict[str, Any]],
    gts: list[dict[str, Any]],
    iou_threshold: float,
) -> tuple[int, int, int, list[tuple[int, int, float]]]:
    if not preds and not gts:
        return 0, 0, 0, []
    if not preds:
        return 0, 0, len(gts), []
    if not gts:
        return 0, len(preds), 0, []

    candidates: list[tuple[float, int, int]] = []
    for p_idx, pred in enumerate(preds):
        pb = pred["bbox"]
        for g_idx, gt in enumerate(gts):
            score = box_iou(pb, gt["bbox"])
            if score >= iou_threshold:
                candidates.append((score, p_idx, g_idx))

    candidates.sort(reverse=True, key=lambda x: x[0])
    used_p: set[int] = set()
    used_g: set[int] = set()
    matches: list[tuple[int, int, float]] = []

    for score, p_idx, g_idx in candidates:
        if p_idx in used_p or g_idx in used_g:
            continue
        used_p.add(p_idx)
        used_g.add(g_idx)
        matches.append((p_idx, g_idx, score))

    tp = len(matches)
    fp = len(preds) - tp
    fn = len(gts) - tp
    return tp, fp, fn, matches


def reading_order_accuracy(
    preds: list[dict[str, Any]],
    gts: list[dict[str, Any]],
    matches: list[tuple[int, int, float]],
) -> float | None:
    if len(matches) <= 1:
        return None

    gt_order_by_idx = {idx: int(gt.get("order", idx + 1)) for idx, gt in enumerate(gts)}
    pred_sorted_idxs = [
        idx
        for idx, _ in sorted(
            ((i, pred) for i, pred in enumerate(preds)),
            key=lambda x: (float(x[1]["bbox"]["y"]), float(x[1]["bbox"]["x"])),
        )
    ]

    matched_gt_orders: list[int] = []
    pair_map = {p: g for p, g, _ in matches}
    for p_idx in pred_sorted_idxs:
        if p_idx in pair_map:
            matched_gt_orders.append(gt_order_by_idx[pair_map[p_idx]])

    if len(matched_gt_orders) <= 1:
        return None

    expected = sorted(matched_gt_orders)
    correct = sum(1 for i, val in enumerate(matched_gt_orders) if val == expected[i])
    return correct / len(expected)


def words_to_line_boxes(words: list[dict[str, Any]], y_tolerance: float = 3.5) -> list[dict[str, float]]:
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: (float(w.get("top", 0.0)), float(w.get("x0", 0.0))))
    lines: list[list[dict[str, Any]]] = []

    for word in words_sorted:
        top = float(word.get("top", 0.0))
        if not lines:
            lines.append([word])
            continue
        current = lines[-1]
        current_top = float(current[-1].get("top", 0.0))
        if abs(top - current_top) <= y_tolerance:
            current.append(word)
        else:
            lines.append([word])

    boxes: list[dict[str, float]] = []
    for line_words in lines:
        x0 = min(float(w.get("x0", 0.0)) for w in line_words)
        x1 = max(float(w.get("x1", 0.0)) for w in line_words)
        top = min(float(w.get("top", 0.0)) for w in line_words)
        bottom = max(float(w.get("bottom", top + 1.0)) for w in line_words)
        boxes.append({"x": x0, "y": top, "w": max(1.0, x1 - x0), "h": max(1.0, bottom - top)})

    return boxes


def scale_boxes_to_image(
    boxes: list[dict[str, float]],
    pdf_w: float,
    pdf_h: float,
    img_w: int,
    img_h: int,
) -> list[dict[str, float]]:
    if pdf_w <= 0 or pdf_h <= 0:
        return []
    sx = img_w / float(pdf_w)
    sy = img_h / float(pdf_h)
    out: list[dict[str, float]] = []
    for b in boxes:
        out.append(
            {
                "x": float(max(0.0, b["x"] * sx)),
                "y": float(max(0.0, b["y"] * sy)),
                "w": float(max(1.0, b["w"] * sx)),
                "h": float(max(1.0, b["h"] * sy)),
            }
        )
    return out


def baseline_native_text_boxes(page_item: dict[str, Any], raw_pages_dir: Path) -> list[dict[str, Any]]:
    source_pdf = Path(str(page_item["source_pdf"]))
    source_page = int(page_item["source_page"])
    page_png = raw_pages_dir / str(page_item["filename"])

    if not source_pdf.exists() or not page_png.exists():
        return []

    with Image.open(page_png) as img:
        img_w, img_h = img.size

    with pdfplumber.open(str(source_pdf)) as pdf:
        if source_page < 1 or source_page > len(pdf.pages):
            return []
        page = pdf.pages[source_page - 1]
        words = page.extract_words(x_tolerance=1, y_tolerance=1, use_text_flow=True) or []
        line_boxes_pdf = words_to_line_boxes(words)
        line_boxes_img = scale_boxes_to_image(line_boxes_pdf, float(page.width), float(page.height), img_w, img_h)

    out: list[dict[str, Any]] = []
    for idx, box in enumerate(line_boxes_img, start=1):
        out.append(
            {
                "id": f"{page_item['page_id']}_pred_line_{idx:03d}",
                "bbox": box,
                "order": idx,
            }
        )
    return out


def x_overlap_ratio(a: dict[str, float], b: dict[str, float]) -> float:
    ax1, ax2 = a["x"], a["x"] + a["w"]
    bx1, bx2 = b["x"], b["x"] + b["w"]
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    denom = max(1.0, min(a["w"], b["w"]))
    return inter / denom


def lightweight_block_merge(
    baseline_boxes: list[dict[str, Any]],
    max_vertical_gap: float = 28.0,
    min_x_overlap_ratio: float = 0.3,
) -> list[dict[str, Any]]:
    if not baseline_boxes:
        return []

    ordered = sorted(baseline_boxes, key=lambda b: (float(b["bbox"]["y"]), float(b["bbox"]["x"])))
    merged: list[dict[str, float]] = []

    for item in ordered:
        box = dict(item["bbox"])
        if not merged:
            merged.append(box)
            continue

        prev = merged[-1]
        prev_bottom = prev["y"] + prev["h"]
        gap = box["y"] - prev_bottom
        overlap = x_overlap_ratio(prev, box)

        if gap <= max_vertical_gap and overlap >= min_x_overlap_ratio:
            nx1 = min(prev["x"], box["x"])
            ny1 = min(prev["y"], box["y"])
            nx2 = max(prev["x"] + prev["w"], box["x"] + box["w"])
            ny2 = max(prev["y"] + prev["h"], box["y"] + box["h"])
            merged[-1] = {"x": nx1, "y": ny1, "w": max(1.0, nx2 - nx1), "h": max(1.0, ny2 - ny1)}
        else:
            merged.append(box)

    out: list[dict[str, Any]] = []
    for idx, box in enumerate(merged, start=1):
        out.append({"id": f"merged_block_{idx:03d}", "bbox": box, "order": idx})
    return out


def load_precomputed_segments(path: Path) -> dict[str, list[dict[str, Any]]]:
    obj = read_json(path)
    pages = obj.get("pages", {}) if isinstance(obj, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    if isinstance(pages, dict):
        for page_id, payload in pages.items():
            blocks = payload.get("blocks", []) if isinstance(payload, dict) else []
            normalized: list[dict[str, Any]] = []
            for idx, block in enumerate(blocks, start=1):
                bbox = dict(block.get("bbox", {})) if isinstance(block, dict) else {}
                if not all(k in bbox for k in ("x", "y", "w", "h")):
                    continue
                normalized.append(
                    {
                        "id": str(block.get("id", f"{page_id}_seg_{idx:03d}")),
                        "bbox": {
                            "x": float(bbox["x"]),
                            "y": float(bbox["y"]),
                            "w": float(bbox["w"]),
                            "h": float(bbox["h"]),
                        },
                        "order": int(block.get("order", idx)),
                    }
                )
            out[str(page_id)] = normalized
    return out


def evaluate_method(
    method_name: str,
    manifest_pages: list[dict[str, Any]],
    gt_map: dict[str, list[dict[str, Any]]],
    predictor: Callable[[dict[str, Any]], list[dict[str, Any]]],
    iou_threshold: float,
) -> dict[str, Any]:
    tp_total = 0
    fp_total = 0
    fn_total = 0
    page_count_labeled = 0
    order_scores: list[float] = []
    page_timings_ms: list[float] = []
    page_peak_mem_mb: list[float] = []

    for page_item in manifest_pages:
        page_id = str(page_item["page_id"])
        gts = gt_map.get(page_id, [])
        if not gts:
            continue

        tracemalloc.start()
        t0 = time.perf_counter()
        preds = predictor(page_item)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tp, fp, fn, matches = greedy_matches(preds, gts, iou_threshold=iou_threshold)
        tp_total += tp
        fp_total += fp
        fn_total += fn
        page_count_labeled += 1
        page_timings_ms.append(elapsed_ms)
        page_peak_mem_mb.append(float(peak) / (1024.0 * 1024.0))

        ro_acc = reading_order_accuracy(preds, gts, matches)
        if ro_acc is not None:
            order_scores.append(ro_acc)

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "method": method_name,
        "labeled_pages_evaluated": page_count_labeled,
        "block_metrics": {
            "tp": tp_total,
            "fp": fp_total,
            "fn": fn_total,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "iou_threshold": iou_threshold,
        },
        "reading_order_accuracy": {
            "mean": statistics.mean(order_scores) if order_scores else None,
            "pages_scored": len(order_scores),
        },
        "runtime": {
            "mean_ms_per_page": statistics.mean(page_timings_ms) if page_timings_ms else None,
            "p95_ms_per_page":
                sorted(page_timings_ms)[int(0.95 * (len(page_timings_ms) - 1))] if len(page_timings_ms) > 1 else (page_timings_ms[0] if page_timings_ms else None),
        },
        "memory": {
            "mean_peak_mb_per_page": statistics.mean(page_peak_mem_mb) if page_peak_mem_mb else None,
            "max_peak_mb_per_page": max(page_peak_mem_mb) if page_peak_mem_mb else None,
        },
    }


def evaluate_downstream_extraction_quality(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "extraction_dir": str(path),
            "present": False,
            "message": "Extraction directory not found; downstream quality check skipped.",
        }

    page_files = sorted(path.glob("page_*.json"))
    events = 0
    evidence_rows = 0
    missing_entity_links = 0
    missing_bbox_links = 0

    for page_file in page_files:
        packet = read_json(page_file)
        for event in list(packet.get("events", [])):
            if not isinstance(event, dict):
                continue
            events += 1
            for ev in list(event.get("evidence", [])):
                if not isinstance(ev, dict):
                    continue
                evidence_rows += 1
                if not str(ev.get("entity_id", "")).strip() or str(ev.get("entity_id", "")).strip().lower() == "missing":
                    missing_entity_links += 1
                if not str(ev.get("bbox_id", "")).strip() or str(ev.get("bbox_id", "")).strip().lower() == "missing":
                    missing_bbox_links += 1

    entity_link_completeness = (
        1.0 - (missing_entity_links / evidence_rows) if evidence_rows else None
    )
    bbox_link_completeness = (
        1.0 - (missing_bbox_links / evidence_rows) if evidence_rows else None
    )

    return {
        "extraction_dir": str(path),
        "present": True,
        "page_files": len(page_files),
        "events": events,
        "evidence_rows": evidence_rows,
        "missing_entity_links": missing_entity_links,
        "missing_bbox_links": missing_bbox_links,
        "entity_link_completeness": entity_link_completeness,
        "bbox_link_completeness": bbox_link_completeness,
    }


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    cfg = read_json(config_path)

    case_id = str(cfg.get("case_id", "UNKNOWN_CASE"))
    base_dir = config_path_value(cfg["base_dir"]).resolve()
    manifest_path = config_path_value(
        cfg.get("render_manifest", base_dir / "pages" / "raw" / "render_manifest.json")
    ).resolve()
    gt_path = config_path_value(cfg["ground_truth"])
    if not gt_path.is_absolute():
        gt_path = (config_path.parent / gt_path).resolve()

    output_raw = args.out or cfg.get("output", "../results/segmentation_benchmark_output.json")
    output_path = config_path_value(output_raw)
    if not output_path.is_absolute():
        output_path = (config_path.parent / output_path).resolve()
    else:
        output_path = output_path.resolve()

    if not manifest_path.exists():
        raise SystemExit(f"Render manifest not found: {manifest_path}")
    if not gt_path.exists():
        raise SystemExit(f"Ground truth file not found: {gt_path}")

    raw_pages_dir = manifest_path.parent
    manifest = read_json(manifest_path)
    manifest_pages = list(manifest.get("pages", []))
    gt_map = load_ground_truth(gt_path)

    iou_threshold = float(dict(cfg.get("evaluation", {})).get("iou_threshold", 0.5))

    baseline_predictor = lambda page_item: baseline_native_text_boxes(page_item, raw_pages_dir)
    baseline = evaluate_method(
        method_name="baseline_native_text",
        manifest_pages=manifest_pages,
        gt_map=gt_map,
        predictor=baseline_predictor,
        iou_threshold=iou_threshold,
    )

    segmentation_cfg = dict(cfg.get("segmentation", {}))
    seg_enabled = bool(segmentation_cfg.get("enabled", False))
    feature_flag_env = str(segmentation_cfg.get("feature_flag_env", "SEGMENTATION_RESEARCH_V2")).strip()
    require_feature_flag = bool(segmentation_cfg.get("require_feature_flag", True))
    flag_ok = os.getenv(feature_flag_env, "0") == "1"

    segmentation_result: dict[str, Any] = {
        "method": "segmentation_assisted",
        "enabled": seg_enabled,
        "skipped": True,
        "reason": "Segmentation disabled in config.",
    }

    if seg_enabled and (not require_feature_flag or flag_ok):
        provider = str(segmentation_cfg.get("provider", "lightweight_block_merge"))

        if provider == "lightweight_block_merge":
            max_gap = float(segmentation_cfg.get("max_vertical_gap", 28.0))
            min_overlap = float(segmentation_cfg.get("min_x_overlap_ratio", 0.3))
            predictor = lambda page_item: lightweight_block_merge(
                baseline_predictor(page_item),
                max_vertical_gap=max_gap,
                min_x_overlap_ratio=min_overlap,
            )
            result = evaluate_method(
                method_name="segmentation_lightweight_block_merge",
                manifest_pages=manifest_pages,
                gt_map=gt_map,
                predictor=predictor,
                iou_threshold=iou_threshold,
            )
            result["enabled"] = True
            result["skipped"] = False
            result["provider"] = provider
            segmentation_result = result

        elif provider in {"sam2_precomputed", "sam3_precomputed", "sam_precomputed"}:
            precomputed_path_raw = segmentation_cfg.get("precomputed_segments")
            if not precomputed_path_raw:
                segmentation_result = {
                    "method": "segmentation_assisted",
                    "enabled": True,
                    "skipped": True,
                    "provider": provider,
                    "reason": "precomputed_segments path is required for *_precomputed provider.",
                }
            else:
                precomputed_path = config_path_value(precomputed_path_raw)
                if not precomputed_path.is_absolute():
                    precomputed_path = (config_path.parent / precomputed_path).resolve()
                segments = load_precomputed_segments(precomputed_path)
                predictor = lambda page_item: list(segments.get(str(page_item["page_id"]), []))
                result = evaluate_method(
                    method_name=f"segmentation_{provider}",
                    manifest_pages=manifest_pages,
                    gt_map=gt_map,
                    predictor=predictor,
                    iou_threshold=iou_threshold,
                )
                result["enabled"] = True
                result["skipped"] = False
                result["provider"] = provider
                result["precomputed_segments"] = str(precomputed_path)
                segmentation_result = result
        else:
            segmentation_result = {
                "method": "segmentation_assisted",
                "enabled": True,
                "skipped": True,
                "provider": provider,
                "reason": "Unsupported segmentation provider. Use lightweight_block_merge or *_precomputed providers.",
            }
    elif seg_enabled:
        segmentation_result = {
            "method": "segmentation_assisted",
            "enabled": True,
            "skipped": True,
            "reason": f"Feature flag {feature_flag_env}=1 required.",
            "feature_flag_env": feature_flag_env,
        }

    downstream_cfg = dict(cfg.get("downstream_quality", {}))
    extraction_dir_raw = downstream_cfg.get("extractions_reconciled")
    downstream = None
    if extraction_dir_raw:
        extraction_dir = config_path_value(extraction_dir_raw).resolve()
        downstream = evaluate_downstream_extraction_quality(extraction_dir)

    output = {
        "case_id": case_id,
        "base_dir": str(base_dir),
        "render_manifest": str(manifest_path),
        "ground_truth": str(gt_path),
        "pages_in_manifest": len(manifest_pages),
        "pages_with_labels": sum(1 for p in manifest_pages if str(p.get("page_id", "")) in gt_map),
        "baseline": baseline,
        "segmentation": segmentation_result,
        "downstream_quality": downstream,
        "notes": [
            "This benchmark harness is Iteration 2 research only.",
            "v1 production pipeline remains unchanged.",
            "For SAM-family runs, use sam2_precomputed or sam3_precomputed with externally generated segments.",
        ],
    }

    write_json(output_path, output)

    if args.print_summary:
        b = baseline["block_metrics"]
        print(
            f"baseline precision={b['precision']:.4f} recall={b['recall']:.4f} "
            f"f1={b['f1']:.4f} pages={baseline['labeled_pages_evaluated']}"
        )
        if not segmentation_result.get("skipped", True):
            s = dict(segmentation_result.get("block_metrics", {}))
            print(
                f"segmentation precision={s.get('precision', 0.0):.4f} "
                f"recall={s.get('recall', 0.0):.4f} f1={s.get('f1', 0.0):.4f}"
            )
        else:
            print(f"segmentation skipped: {segmentation_result.get('reason')}")
        print(f"output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
