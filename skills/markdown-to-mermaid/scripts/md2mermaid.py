#!/usr/bin/env python3
"""
Convert structured markdown into Mermaid diagrams.
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert markdown to Mermaid")
    parser.add_argument("--input", required=True, help="Input markdown file")
    parser.add_argument("--output", default=None, help="Output file (.mmd or .md)")
    parser.add_argument("--type", default="auto", choices=["auto", "flowchart", "sequence", "state", "gantt", "mindmap"], help="Diagram type")
    parser.add_argument("--embed", action="store_true", help="Wrap output in ```mermaid fence")
    parser.add_argument("--title", default=None, help="Optional diagram title override")
    return parser.parse_args()


def extract_mermaid_block(text: str) -> str | None:
    match = re.search(r"```mermaid\s*(.*?)```", text, re.S | re.I)
    if match:
        return match.group(1).strip()
    return None


def detect_type(text: str) -> str:
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return "gantt"
    if re.search(r"^\s*\d+[\.)]\s+", text, re.M):
        return "sequence"
    if re.search(r"->|→", text):
        return "state"
    if re.search(r"^\s*[-*+]\s+", text, re.M):
        return "flowchart"
    return "mindmap"


def sanitize_label(label: str) -> str:
    clean = re.sub(r"\s+", " ", label.strip())
    clean = clean.replace('"', "'")
    return clean or "Item"


def render_flowchart(text: str, title: str | None) -> str:
    nodes: List[Tuple[str, str]] = []
    edges: List[Tuple[str, str]] = []
    stack: Dict[int, str] = {}
    node_id = 0
    current_heading_id: str | None = None

    def new_id() -> str:
        nonlocal node_id
        node_id += 1
        return f"N{node_id}"

    for line in text.splitlines():
        if not line.strip():
            continue

        heading = re.match(r"^(#+)\s+(.*)$", line)
        if heading:
            label = sanitize_label(heading.group(2))
            node = new_id()
            nodes.append((node, label))
            stack = {0: node}
            current_heading_id = node
            continue

        bullet = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if bullet:
            indent = len(bullet.group(1).replace("\t", "  "))
            bullet_level = indent // 2
            base_depth = 1 if current_heading_id else 0
            depth = base_depth + bullet_level

            label = sanitize_label(bullet.group(2))
            node = new_id()
            nodes.append((node, label))

            parent = stack.get(depth - 1)
            if parent is None and current_heading_id and depth == 1:
                parent = current_heading_id

            if parent:
                edges.append((parent, node))

            stack[depth] = node
            continue

    if not nodes:
        nodes.append(("N1", title or "Diagram"))

    lines: List[str] = ["flowchart TD"]
    for node, label in nodes:
        lines.append(f"    {node}[{label}]")
    for src, dst in edges:
        lines.append(f"    {src} --> {dst}")
    return "\n".join(lines)


def render_sequence(text: str, title: str | None) -> str:
    steps: List[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*\d+[\.)]\s+(.*)$", line)
        if match:
            steps.append(match.group(1).strip())

    if not steps:
        return "sequenceDiagram\n    participant User\n    participant System\n    User->>System: No steps found"

    participants: Dict[str, str] = {}
    order: List[str] = []

    def get_id(name: str) -> str:
        if name not in participants:
            pid = re.sub(r"[^A-Za-z0-9]", "", name) or "P"
            if pid in participants.values():
                pid = f"P{len(participants) + 1}"
            participants[name] = pid
            order.append(name)
        return participants[name]

    messages: List[Tuple[str, str, str]] = []
    for step in steps:
        arrow = re.match(r"(.+?)\s*(?:--?>|→)\s*(.+?)(?::\s*(.*))?$", step)
        if arrow:
            src_name = sanitize_label(arrow.group(1))
            dst_name = sanitize_label(arrow.group(2))
            msg = sanitize_label(arrow.group(3) or "")
        else:
            actor = re.match(r"(.+?):\s*(.*)$", step)
            if actor:
                src_name = sanitize_label(actor.group(1))
                dst_name = "System"
                msg = sanitize_label(actor.group(2))
            else:
                src_name = "User"
                dst_name = "System"
                msg = sanitize_label(step)

        src_id = get_id(src_name)
        dst_id = get_id(dst_name)
        messages.append((src_id, dst_id, msg))

    lines: List[str] = ["sequenceDiagram"]
    for name in order:
        lines.append(f"    participant {participants[name]} as \"{name}\"")
    for src, dst, msg in messages:
        lines.append(f"    {src}->>{dst}: {msg}")
    return "\n".join(lines)


def render_state(text: str, title: str | None) -> str:
    transitions: List[Tuple[str, str, str | None]] = []
    for line in text.splitlines():
        match = re.match(r"^\s*[-*+]?\s*(.+?)\s*(?:--?>|→)\s*(.+?)(?:\s*(?:\(|:)?\s*on:?\s*([^)]*))?$", line)
        if match:
            src = sanitize_label(match.group(1))
            dst = sanitize_label(match.group(2))
            event = sanitize_label(match.group(3) or "") if match.group(3) else None
            transitions.append((src, dst, event))

    if not transitions:
        return "stateDiagram-v2\n    [*] --> Idle"

    lines: List[str] = ["stateDiagram-v2"]
    first_src = transitions[0][0]
    lines.append(f"    [*] --> {first_src}")
    for src, dst, event in transitions:
        if event:
            lines.append(f"    {src} --> {dst} : {event}")
        else:
            lines.append(f"    {src} --> {dst}")
    return "\n".join(lines)


def render_gantt(text: str, title: str | None) -> str:
    tasks: List[Tuple[str, str, str, str]] = []
    task_id = 0
    for line in text.splitlines():
        match = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})", line)
        if not match:
            continue

        start, end = match.group(1), match.group(2)
        label = re.sub(r"\(.*?\)", "", line)
        label = re.sub(r"\d{4}-\d{2}-\d{2}", "", label)
        label = sanitize_label(label.strip("- "))

        status = ""
        lowered = line.lower()
        if "done" in lowered:
            status = "done, "
        elif "active" in lowered:
            status = "active, "

        task_id += 1
        tasks.append((label or f"Task {task_id}", start, end, status))

    lines: List[str] = ["gantt", f"    title {title or 'Project Timeline'}", "    dateFormat YYYY-MM-DD", "    section Tasks"]
    for idx, (label, start, end, status) in enumerate(tasks, start=1):
        lines.append(f"    {label} :{status}t{idx}, {start}, {end}")
    return "\n".join(lines)


def render_mindmap(text: str, title: str | None) -> str:
    lines: List[str] = ["mindmap", f"  root(({title or 'Mind Map'}))"]
    for line in text.splitlines():
        heading = re.match(r"^(#+)\s+(.*)$", line)
        if heading:
            depth = max(1, len(heading.group(1)))
            label = sanitize_label(heading.group(2))
            lines.append("  " + "  " * depth + label)
            continue
        bullet = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if bullet:
            indent = len(bullet.group(1).replace("\t", "  "))
            depth = max(1, indent // 2 + 1)
            label = sanitize_label(bullet.group(2))
            lines.append("  " + "  " * depth + label)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    with open(args.input, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()

    title = args.title
    if title is None:
        for line in text.splitlines():
            match = re.match(r"^#\s+(.*)$", line)
            if match:
                title = sanitize_label(match.group(1))
                break
    if title is None:
        title = os.path.splitext(os.path.basename(args.input))[0].replace("_", " ").title()

    existing = extract_mermaid_block(text)
    if existing:
        diagram = existing
    else:
        diagram_type = args.type if args.type != "auto" else detect_type(text)
        if diagram_type == "sequence":
            diagram = render_sequence(text, title)
        elif diagram_type == "state":
            diagram = render_state(text, title)
        elif diagram_type == "gantt":
            diagram = render_gantt(text, title)
        elif diagram_type == "mindmap":
            diagram = render_mindmap(text, title)
        else:
            diagram = render_flowchart(text, title)

    if args.embed:
        output = f"```mermaid\n{diagram}\n```\n"
    else:
        output = diagram + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
