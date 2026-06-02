#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import html
import re
import sys
import textwrap
from typing import Iterable, List, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class Node:
    node_id: str
    depth: int
    label: str
    kind: str  # heading | item | text
    parent_id: Optional[str]


@dataclasses.dataclass(frozen=True)
class LaidOutNode:
    node: Node
    x: float
    y: float
    width: float
    height: float
    lines: List[str]


HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")
BULLET_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<bullet>[-*+]|(\d+\.))\s+(?P<text>.+?)\s*$")


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _indent_depth(indent: str, tab_width: int) -> int:
    depth = 0
    for ch in indent:
        if ch == "\t":
            depth += tab_width
        else:
            depth += 1
    return depth


def parse_outline(text: str, *, tab_width: int = 2, indent_size: int = 2) -> List[Node]:
    nodes: List[Node] = []
    last_at_depth: dict[int, str] = {}
    current_heading_depth: Optional[int] = None

    lines = text.splitlines()
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group("hashes"))
            label = heading_match.group("text").strip()
            depth = max(0, level - 1)
            parent_id = None
            for d in range(depth - 1, -1, -1):
                if d in last_at_depth:
                    parent_id = last_at_depth[d]
                    break
            node_id = f"n{len(nodes) + 1}"
            node = Node(node_id=node_id, depth=depth, label=label, kind="heading", parent_id=parent_id)
            nodes.append(node)
            last_at_depth[depth] = node_id
            for d in list(last_at_depth.keys()):
                if d > depth:
                    del last_at_depth[d]
            current_heading_depth = depth
            continue

        bullet_match = BULLET_RE.match(line)
        if bullet_match:
            indent = bullet_match.group("indent") or ""
            label = bullet_match.group("text").strip()
            indent_depth = _indent_depth(indent, tab_width)
            rel_depth = indent_depth // max(1, indent_size)
            base = (current_heading_depth + 1) if current_heading_depth is not None else 0
            depth = base + rel_depth
            parent_id = None
            for d in range(depth - 1, -1, -1):
                if d in last_at_depth:
                    parent_id = last_at_depth[d]
                    break
            node_id = f"n{len(nodes) + 1}"
            node = Node(node_id=node_id, depth=depth, label=label, kind="item", parent_id=parent_id)
            nodes.append(node)
            last_at_depth[depth] = node_id
            for d in list(last_at_depth.keys()):
                if d > depth:
                    del last_at_depth[d]
            continue

        indent_depth = _indent_depth(line[: len(line) - len(line.lstrip(" \t"))], tab_width)
        rel_depth = indent_depth // max(1, indent_size)
        base = (current_heading_depth + 1) if current_heading_depth is not None else 0
        depth = base + rel_depth
        label = line.strip()

        parent_id = None
        for d in range(depth - 1, -1, -1):
            if d in last_at_depth:
                parent_id = last_at_depth[d]
                break

        node_id = f"n{len(nodes) + 1}"
        node = Node(node_id=node_id, depth=depth, label=label, kind="text", parent_id=parent_id)
        nodes.append(node)
        last_at_depth[depth] = node_id
        for d in list(last_at_depth.keys()):
            if d > depth:
                del last_at_depth[d]

    return nodes


def _wrap_label(label: str, *, max_chars: int) -> List[str]:
    label = re.sub(r"\s+", " ", label.strip())
    if not label:
        return [""]
    if max_chars <= 4:
        return [label[: max(1, max_chars)]]
    return textwrap.wrap(label, width=max_chars, break_long_words=True, break_on_hyphens=True) or [label]


def layout_nodes(
    nodes: List[Node],
    *,
    node_width: int,
    font_size: int,
    pad_x: int,
    pad_y: int,
    v_gap: int,
    h_gap: int,
    margin: int,
    char_width: float,
    max_depth: Optional[int] = None,
) -> Tuple[List[LaidOutNode], float, float]:
    laid_out: List[LaidOutNode] = []
    current_y = float(margin)

    effective_nodes = nodes if max_depth is None else [n for n in nodes if n.depth <= max_depth]

    for node in effective_nodes:
        max_chars = max(5, int((node_width - 2 * pad_x) / max(1.0, char_width)))
        lines = _wrap_label(node.label, max_chars=max_chars)
        line_height = font_size * 1.25
        height = 2 * pad_y + line_height * len(lines)
        x = float(margin + node.depth * (node_width + h_gap))
        y = current_y
        current_y = y + height + v_gap
        laid_out.append(
            LaidOutNode(node=node, x=x, y=y, width=float(node_width), height=float(height), lines=lines)
        )

    max_x = max((n.x + n.width for n in laid_out), default=float(margin))
    max_y = max((n.y + n.height for n in laid_out), default=float(margin))
    canvas_width = max_x + margin
    canvas_height = max_y + margin
    return laid_out, canvas_width, canvas_height


def _svg_escape(text: str) -> str:
    return html.escape(text, quote=True)


def _node_style(kind: str) -> Tuple[str, str]:
    if kind == "heading":
        return ("node-heading", "#1f2937")
    if kind == "item":
        return ("node-item", "#0f172a")
    return ("node-text", "#111827")


def _emit_svg(
    title: str,
    laid_out: List[LaidOutNode],
    *,
    canvas_width: float,
    canvas_height: float,
    font_family: str,
    font_size: int,
    pad_x: int,
    pad_y: int,
    h_gap: int,
    include_js: bool,
    grid_size: int,
) -> str:
    by_id = {n.node.node_id: n for n in laid_out}

    # Edges (parent -> child)
    edges: List[Tuple[LaidOutNode, LaidOutNode]] = []
    for child in laid_out:
        if child.node.parent_id and child.node.parent_id in by_id:
            edges.append((by_id[child.node.parent_id], child))

    def center_y(n: LaidOutNode) -> float:
        return n.y + (n.height / 2.0)

    svg_parts: List[str] = []
    svg_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{int(canvas_width)}" height="{int(canvas_height)}" '
        f'viewBox="0 0 {int(canvas_width)} {int(canvas_height)}" '
        f'role="img" aria-label="{_svg_escape(title)}">'
    )
    svg_parts.append("<defs>")
    svg_parts.append(
        f'<style><![CDATA['
        f'  .bg {{ fill: #0b1020; }}'
        f'  .grid {{ stroke: rgba(148,163,184,0.08); stroke-width: 1; }}'
        f'  .edge {{ stroke: rgba(148,163,184,0.35); stroke-width: 1.5; fill: none; }}'
        f'  .edge-strong {{ stroke: rgba(56,189,248,0.55); stroke-width: 2.0; fill: none; }}'
        f'  .node-rect {{ rx: 10; ry: 10; stroke: rgba(148,163,184,0.35); stroke-width: 1.0; }}'
        f'  .node-heading .node-rect {{ fill: rgba(30,41,59,0.85); }}'
        f'  .node-item .node-rect {{ fill: rgba(15,23,42,0.78); }}'
        f'  .node-text .node-rect {{ fill: rgba(2,6,23,0.68); }}'
        f'  .node-label {{ font-family: {font_family}; font-size: {font_size}px; dominant-baseline: hanging; }}'
        f'  .node-heading .node-label {{ font-weight: 700; fill: #e2e8f0; }}'
        f'  .node-item .node-label {{ font-weight: 600; fill: #cbd5e1; }}'
        f'  .node-text .node-label {{ font-weight: 500; fill: #cbd5e1; }}'
        f'  .node:hover .node-rect {{ stroke: rgba(56,189,248,0.9); }}'
        f'  .title {{ font-family: {font_family}; font-size: {max(14, font_size + 4)}px; fill: #e2e8f0; font-weight: 700; }}'
        f'  .hint {{ font-family: {font_family}; font-size: {max(10, font_size - 2)}px; fill: rgba(203,213,225,0.7); }}'
        f']]></style>'
    )
    svg_parts.append("</defs>")

    svg_parts.append(f'<rect class="bg" x="0" y="0" width="{int(canvas_width)}" height="{int(canvas_height)}"/>')

    if grid_size > 0:
        for x in range(0, int(canvas_width) + 1, grid_size):
            svg_parts.append(f'<line class="grid" x1="{x}" y1="0" x2="{x}" y2="{int(canvas_height)}"/>')
        for y in range(0, int(canvas_height) + 1, grid_size):
            svg_parts.append(f'<line class="grid" x1="0" y1="{y}" x2="{int(canvas_width)}" y2="{y}"/>')

    svg_parts.append('<g id="viewport">')
    svg_parts.append(f'<text class="title" x="{pad_x}" y="{pad_y}">{_svg_escape(title)}</text>')
    svg_parts.append(
        f'<text class="hint" x="{pad_x}" y="{pad_y + max(18, font_size + 8)}">'
        f'Wheel to zoom • Drag to pan • Click a node to center • Double-click background to fit'
        f"</text>"
    )

    for parent, child in edges:
        x1 = parent.x + parent.width
        y1 = center_y(parent)
        x2 = child.x
        y2 = center_y(child)
        c1x = x1 + max(30.0, float(h_gap) * 0.5)
        c2x = x2 - max(30.0, float(h_gap) * 0.5)
        cls = "edge-strong" if parent.node.kind == "heading" else "edge"
        svg_parts.append(
            f'<path class="{cls}" d="M {x1:.1f},{y1:.1f} C {c1x:.1f},{y1:.1f} {c2x:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"/>'
        )

    for n in laid_out:
        node_class, _ = _node_style(n.node.kind)
        cx = n.x + (n.width / 2.0)
        cy = n.y + (n.height / 2.0)
        svg_parts.append(
            f'<g class="node {node_class}" id="{n.node.node_id}" data-cx="{cx:.1f}" data-cy="{cy:.1f}">'
        )
        svg_parts.append(
            f'<rect class="node-rect" x="{n.x:.1f}" y="{n.y:.1f}" width="{n.width:.1f}" height="{n.height:.1f}"/>'
        )
        text_x = n.x + pad_x
        text_y = n.y + pad_y
        svg_parts.append(f'<text class="node-label" x="{text_x:.1f}" y="{text_y:.1f}">')
        dy = 0.0
        for line in n.lines:
            svg_parts.append(f'<tspan x="{text_x:.1f}" dy="{dy:.1f}">{_svg_escape(line)}</tspan>')
            dy = font_size * 1.25
        svg_parts.append("</text>")
        svg_parts.append(f"<title>{_svg_escape(n.node.label)}</title>")
        svg_parts.append("</g>")

    svg_parts.append("</g>")

    if include_js:
        svg_parts.append(
            "<script><![CDATA[\n"
            "(function(){\n"
            "  const svg = document.documentElement;\n"
            "  const viewport = document.getElementById('viewport');\n"
            "  let viewBox = svg.viewBox.baseVal;\n"
            "  function setViewBox(x,y,w,h){ viewBox.x=x; viewBox.y=y; viewBox.width=w; viewBox.height=h; }\n"
            "  function svgPoint(evt){\n"
            "    const pt = svg.createSVGPoint();\n"
            "    pt.x = evt.clientX; pt.y = evt.clientY;\n"
            "    const ctm = svg.getScreenCTM();\n"
            "    if(!ctm) return {x:0,y:0};\n"
            "    const p = pt.matrixTransform(ctm.inverse());\n"
            "    return {x:p.x,y:p.y};\n"
            "  }\n"
            "  function fitToContent(){\n"
            "    const bb = viewport.getBBox();\n"
            "    const m = 40;\n"
            "    setViewBox(bb.x-m, bb.y-m, bb.width+2*m, bb.height+2*m);\n"
            "  }\n"
            "  let dragging = false;\n"
            "  let dragStart = null;\n"
            "  let vbStart = null;\n"
            "  svg.addEventListener('mousedown', (e)=>{\n"
            "    if(e.button !== 0) return;\n"
            "    dragging = true;\n"
            "    dragStart = svgPoint(e);\n"
            "    vbStart = {x:viewBox.x, y:viewBox.y, w:viewBox.width, h:viewBox.height};\n"
            "  });\n"
            "  svg.addEventListener('mousemove', (e)=>{\n"
            "    if(!dragging || !dragStart || !vbStart) return;\n"
            "    const p = svgPoint(e);\n"
            "    const dx = p.x - dragStart.x;\n"
            "    const dy = p.y - dragStart.y;\n"
            "    setViewBox(vbStart.x - dx, vbStart.y - dy, vbStart.w, vbStart.h);\n"
            "  });\n"
            "  svg.addEventListener('mouseup', ()=>{ dragging=false; dragStart=null; vbStart=null; });\n"
            "  svg.addEventListener('mouseleave', ()=>{ dragging=false; dragStart=null; vbStart=null; });\n"
            "  svg.addEventListener('wheel', (e)=>{\n"
            "    e.preventDefault();\n"
            "    const p = svgPoint(e);\n"
            "    const zoom = Math.exp(-e.deltaY * 0.0015);\n"
            "    const newW = viewBox.width / zoom;\n"
            "    const newH = viewBox.height / zoom;\n"
            "    const rx = (p.x - viewBox.x) / viewBox.width;\n"
            "    const ry = (p.y - viewBox.y) / viewBox.height;\n"
            "    const newX = p.x - rx * newW;\n"
            "    const newY = p.y - ry * newH;\n"
            "    setViewBox(newX, newY, newW, newH);\n"
            "  }, {passive:false});\n"
            "  svg.addEventListener('dblclick', (e)=>{\n"
            "    if(e.target && e.target.closest && e.target.closest('.node')) return;\n"
            "    fitToContent();\n"
            "  });\n"
            "  svg.addEventListener('click', (e)=>{\n"
            "    const node = e.target && e.target.closest ? e.target.closest('.node') : null;\n"
            "    if(!node) return;\n"
            "    const cx = parseFloat(node.getAttribute('data-cx') || '0');\n"
            "    const cy = parseFloat(node.getAttribute('data-cy') || '0');\n"
            "    setViewBox(cx - viewBox.width/2, cy - viewBox.height/2, viewBox.width, viewBox.height);\n"
            "  });\n"
            "  fitToContent();\n"
            "})();\n"
            "]]></script>"
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts) + "\n"


def write_file_safely(path: str, content: str) -> None:
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    # Atomic on POSIX when same filesystem
    import os

    os.replace(temp_path, path)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a zoomable, sourcemap-style SVG from Markdown/text outlines.")
    p.add_argument("--in", dest="in_path", default="-", help="Input file path, or '-' for stdin.")
    p.add_argument("--out", dest="out_path", required=True, help="Output SVG path.")
    p.add_argument("--title", default="SVG Sourcemap", help="Top-left title text.")
    p.add_argument("--node-width", type=int, default=340, help="Node width in px.")
    p.add_argument("--font-size", type=int, default=12, help="Font size in px.")
    p.add_argument("--font-family", default="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial", help="CSS font-family.")
    p.add_argument("--pad-x", type=int, default=14, help="Node horizontal padding in px.")
    p.add_argument("--pad-y", type=int, default=10, help="Node vertical padding in px.")
    p.add_argument("--v-gap", type=int, default=12, help="Vertical gap between nodes in px.")
    p.add_argument("--h-gap", type=int, default=140, help="Horizontal gap between depth columns in px.")
    p.add_argument("--margin", type=int, default=60, help="Canvas margin in px.")
    p.add_argument("--grid-size", type=int, default=80, help="Grid size in px; 0 disables.")
    p.add_argument("--tab-width", type=int, default=2, help="Tab width when computing indentation depth.")
    p.add_argument("--indent-size", type=int, default=2, help="Spaces per indentation level.")
    p.add_argument("--max-depth", type=int, default=None, help="Maximum depth to render (optional).")
    p.add_argument("--no-js", action="store_true", help="Disable embedded pan/zoom/click JS.")
    return p


def main(argv: List[str]) -> int:
    args = build_arg_parser().parse_args(argv)

    source = _read_input(args.in_path)
    nodes = parse_outline(source, tab_width=args.tab_width, indent_size=args.indent_size)
    if not nodes:
        raise SystemExit("No nodes found. Provide Markdown headings/bullets or an indented outline.")

    laid_out, canvas_width, canvas_height = layout_nodes(
        nodes,
        node_width=args.node_width,
        font_size=args.font_size,
        pad_x=args.pad_x,
        pad_y=args.pad_y,
        v_gap=args.v_gap,
        h_gap=args.h_gap,
        margin=args.margin,
        char_width=max(6.0, args.font_size * 0.55),
        max_depth=args.max_depth,
    )

    svg = _emit_svg(
        title=args.title,
        laid_out=laid_out,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        font_family=args.font_family,
        font_size=args.font_size,
        pad_x=args.pad_x,
        pad_y=args.pad_y,
        h_gap=args.h_gap,
        include_js=not args.no_js,
        grid_size=args.grid_size,
    )
    write_file_safely(args.out_path, svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

