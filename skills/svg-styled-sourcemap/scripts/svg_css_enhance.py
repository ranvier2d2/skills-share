#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def _local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _asset_path(rel: str) -> Path:
    # skill_dir/scripts/svg_css_enhance.py -> skill_dir/assets/...
    here = Path(__file__).resolve()
    return here.parent.parent / "assets" / rel


def _load_preset_css(name: str) -> str:
    preset_name = re.sub(r"[^a-z0-9_-]+", "", name.lower())
    preset_path = _asset_path(f"presets/{preset_name}.css")
    if not preset_path.exists():
        available = sorted(p.stem for p in (_asset_path("presets")).glob("*.css"))
        raise SystemExit(f"Unknown preset '{name}'. Available: {', '.join(available) or '(none)'}")
    return _read_text(preset_path)


def _ensure_svg_tree(path: Path) -> Tuple[ET.ElementTree, ET.Element]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise SystemExit(f"Failed to parse SVG XML: {path}: {e}") from e
    root = tree.getroot()
    if _local_name(root.tag) != "svg":
        raise SystemExit(f"Not an SVG root element: {path} (got <{_local_name(root.tag)}>)")
    return tree, root


def _ensure_defs(root: ET.Element) -> ET.Element:
    for child in list(root):
        if _local_name(child.tag) == "defs":
            return child
    defs = ET.Element(_q("defs"))
    # Insert early so it affects later rendering; after metadata if present, else at top.
    insert_at = 0
    children = list(root)
    for i, child in enumerate(children):
        if _local_name(child.tag) == "metadata":
            insert_at = i + 1
            break
    root.insert(insert_at, defs)
    return defs


def _append_style(defs: ET.Element, css: str, *, style_id: str = "svg-css-enhancer") -> None:
    # Remove prior injected style blocks with same id to keep output stable across reruns.
    for child in list(defs):
        if _local_name(child.tag) == "style" and child.get("id") == style_id:
            defs.remove(child)
    style = ET.SubElement(defs, _q("style"), {"id": style_id, "type": "text/css"})
    style.text = "\n" + css.strip() + "\n"


def _iter_svg_elements(root: ET.Element) -> Iterable[ET.Element]:
    # Snapshot first: we mutate the tree in several passes (ids/classes/titles),
    # and ElementTree's live iteration can otherwise walk newly-inserted nodes.
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        if el is root:
            continue
        if _local_name(el.tag) in {"defs", "style", "script", "metadata", "title", "desc"}:
            continue
        yield el


def _append_class(el: ET.Element, cls: str) -> None:
    existing = (el.get("class") or "").strip()
    classes = [c for c in existing.split() if c]
    if cls not in classes:
        classes.append(cls)
        el.set("class", " ".join(classes))


def _safe_id(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9_:\\.:-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "el"


@dataclass(frozen=True)
class Report:
    tag_counts: Dict[str, int]
    ids: int
    classes: int


def _collect_report(root: ET.Element) -> Report:
    tag_counts: Dict[str, int] = {}
    ids = 0
    classes = 0
    for el in _iter_svg_elements(root):
        tag = _local_name(el.tag)
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if el.get("id"):
            ids += 1
        if el.get("class"):
            classes += 1
    return Report(tag_counts=tag_counts, ids=ids, classes=classes)


def _ensure_ids(root: ET.Element, *, prefix: str = "svg") -> int:
    used: set[str] = set()
    for el in _iter_svg_elements(root):
        el_id = el.get("id")
        if el_id:
            used.add(el_id)

    created = 0
    counter = 1
    for el in _iter_svg_elements(root):
        if el.get("id"):
            continue
        base = f"{prefix}-{_safe_id(_local_name(el.tag))}"
        el_id = base
        while el_id in used:
            counter += 1
            el_id = f"{base}-{counter}"
        el.set("id", el_id)
        used.add(el_id)
        created += 1
        counter += 1
    return created


def _add_classes(root: ET.Element) -> int:
    updated = 0
    for el in _iter_svg_elements(root):
        before = el.get("class") or ""
        _append_class(el, "svg-el")
        tag = _local_name(el.tag)
        _append_class(el, f"svg-{tag}")
        if tag == "g":
            _append_class(el, "svg-group")
        if tag == "text":
            _append_class(el, "svg-text")
        if (el.get("class") or "") != before:
            updated += 1
    return updated


def _ensure_titles(root: ET.Element) -> int:
    created = 0
    for el in _iter_svg_elements(root):
        # Title is only useful for visible elements; skip some common non-visual tags.
        tag = _local_name(el.tag)
        if tag in {"clipPath", "mask", "pattern", "linearGradient", "radialGradient", "filter"}:
            continue
        has_title = any(_local_name(c.tag) == "title" for c in list(el))
        if has_title:
            continue
        el_id = el.get("id")
        cls = (el.get("class") or "").strip()
        label = el_id or (cls.split()[0] if cls else tag)
        title = ET.Element(_q("title"))
        title.text = label
        el.insert(0, title)
        created += 1
    return created


def _add_background_rect(root: ET.Element) -> bool:
    # Insert as the first renderable child (but keep defs/metadata first).
    children = list(root)
    for child in children:
        if _local_name(child.tag) == "rect" and (child.get("class") or "").split()[:1] == ["svg-bg"]:
            return False
    rect = ET.Element(_q("rect"), {"class": "svg-bg", "x": "0", "y": "0", "width": "100%", "height": "100%"})
    insert_at = 0
    for i, child in enumerate(children):
        if _local_name(child.tag) in {"defs", "metadata"}:
            insert_at = i + 1
    root.insert(insert_at, rect)
    return True


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    # Minimal pretty-printer; keeps diffs readable without depending on external libs.
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent_xml(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Enhance an SVG by injecting CSS presets and optional element normalization.")
    p.add_argument("--in", dest="in_path", required=True, help="Input SVG path.")
    p.add_argument("--out", dest="out_path", help="Output SVG path. If omitted, prints to stdout.")
    p.add_argument("--preset", default=None, help="CSS preset name from assets/presets (e.g. inspector-dark).")
    p.add_argument("--css", default=None, help="Path to a CSS file to inject (in addition to --preset).")
    p.add_argument("--ensure-ids", action="store_true", help="Add ids to elements that lack them.")
    p.add_argument("--id-prefix", default="svg", help="Prefix for generated ids (used with --ensure-ids).")
    p.add_argument("--add-classes", action="store_true", help="Append helpful classes (svg-el, svg-<tag>, etc).")
    p.add_argument("--ensure-titles", action="store_true", help="Add <title> tooltips when missing.")
    p.add_argument("--add-background", action="store_true", help="Insert a <rect class='svg-bg'> behind content.")
    p.add_argument("--no-pretty", action="store_true", help="Do not pretty-print output XML.")
    p.add_argument("--report", action="store_true", help="Print a summary of tags/ids/classes and exit 0.")
    return p


def main(argv: List[str]) -> int:
    args = build_arg_parser().parse_args(argv)
    in_path = Path(args.in_path).expanduser().resolve()
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    # Register namespaces so ElementTree writes clean SVG.
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    tree, root = _ensure_svg_tree(in_path)

    if args.report:
        rep = _collect_report(root)
        tags = " ".join(f"{k}:{rep.tag_counts[k]}" for k in sorted(rep.tag_counts.keys()))
        print(f"path: {in_path}")
        print(f"elements: {sum(rep.tag_counts.values())}")
        print(f"with_id: {rep.ids}")
        print(f"with_class: {rep.classes}")
        print(f"tags: {tags}")
        return 0

    css_parts: List[str] = []
    if args.preset:
        css_parts.append(_load_preset_css(args.preset))
    if args.css:
        css_parts.append(_read_text(Path(args.css).expanduser().resolve()))
    if css_parts:
        defs = _ensure_defs(root)
        _append_style(defs, "\n\n".join(s.strip() for s in css_parts if s.strip()))

    if args.add_background:
        _add_background_rect(root)

    if args.add_classes:
        _add_classes(root)

    if args.ensure_ids:
        _ensure_ids(root, prefix=args.id_prefix)

    if args.ensure_titles:
        _ensure_titles(root)

    if not args.no_pretty:
        _indent_xml(root)

    out_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if args.out_path:
        out_path = Path(args.out_path).expanduser().resolve()
        out_path.write_bytes(out_bytes)
    else:
        sys.stdout.buffer.write(out_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
