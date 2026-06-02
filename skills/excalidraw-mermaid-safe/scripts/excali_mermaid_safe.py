#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SAFE_CLASS_DEFS = {
    "source": "fill:#E8F0FF,stroke:#3159B8,stroke-width:1.5px,color:#132B63",
    "finding": "fill:#EAF8EE,stroke:#2E7D32,stroke-width:1.5px,color:#17351D",
    "decision": "fill:#FFF4E5,stroke:#B76E00,stroke-width:1.5px,color:#5A3A00",
    "action": "fill:#F1EDFF,stroke:#5B4BC4,stroke-width:1.5px,color:#2B245E",
    "risk": "fill:#FDECEC,stroke:#C62828,stroke-width:1.5px,color:#6D1B1B",
    "neutral": "fill:#F3F4F6,stroke:#6B7280,stroke-width:1.5px,color:#1F2937",
}

GROUP_LABELS = {
    "evidence": "Evidence Inputs",
    "findings": "Capability Findings",
    "decision": "Decision",
    "implementation": "Implementation Delta",
    "other": "Other",
}

GROUP_ROLE = {
    "evidence": "source",
    "findings": "finding",
    "decision": "decision",
    "implementation": "action",
    "other": "neutral",
}

RISK_KEYWORDS = (
    "risk",
    "blocked",
    "error",
    "not observed",
    "405",
    "failed",
    "cannot",
)

UNSUPPORTED_DECLARATIONS = (
    "sequenceDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "classDiagram",
    "gantt",
    "mindmap",
)

MAX_LABEL_CHARS = 96


@dataclass
class Section:
    heading: str
    summaries: List[str]
    group: str


@dataclass
class Node:
    node_id: str
    label: str
    role: str
    group: Optional[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate parser-safe Mermaid for Excalidraw")
    parser.add_argument("--input", required=True, help="Input markdown or mermaid file")
    parser.add_argument("--output", required=True, help="Output .mmd file")
    parser.add_argument("--mode", choices=["auto", "from-markdown", "sanitize-mermaid"], default="auto")
    parser.add_argument("--palette", choices=["safe", "mono"], default="safe")
    parser.add_argument("--layout", choices=["grouped", "flat"], default="grouped")
    parser.add_argument("--max-nodes", type=int, default=40)
    parser.add_argument(
        "--validate",
        choices=["none", "static", "excalidraw", "excalidraw-strict"],
        default="static",
    )
    return parser.parse_args()


def strip_markdown_links(text: str) -> str:
    return re.sub(r"\[([^\[\]]+)\]\(([^)]+)\)", r"\1", text)


def strip_urls(text: str) -> str:
    return re.sub(r"https?://[^\s\]\)\"']+", "", text)


def clean_label(text: str, max_chars: int = MAX_LABEL_CHARS) -> str:
    text = strip_markdown_links(text)
    text = strip_urls(text)
    text = text.replace("`", "")
    text = re.sub(r"[*_]{1,3}", "", text)
    text = re.sub(r"^\s*\[[ xX]\]\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" |")
    text = text.replace('"', "'")
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text or "Item"


def extract_mermaid_block(text: str) -> Optional[str]:
    match = re.search(r"```mermaid\s*(.*?)```", text, re.S | re.I)
    if match:
        return match.group(1).strip()
    return None


def detect_input_mode(text: str) -> str:
    if extract_mermaid_block(text):
        return "sanitize-mermaid"
    first = ""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            break
    if first.startswith("flowchart"):
        return "sanitize-mermaid"
    return "from-markdown"


def classify_group(heading: str) -> str:
    low = heading.lower()
    if any(k in low for k in ("implement", "delta", "transport", "helper", "rollout", "adoption", "next step", "action")):
        return "implementation"
    if any(k in low for k in ("recommend", "decision", "architecture", "why this choice", "option", "tradeoff")):
        return "decision"
    if any(k in low for k in ("source", "validation", "evidence", "task-by-task", "task by task", "network reachability", "input", "context")):
        return "evidence"
    if any(k in low for k in ("capability", "finding", "ranking", "approach", "identified", "risk", "issue")):
        return "findings"
    return "findings"


def clean_table_cells(line: str) -> List[str]:
    if not line.strip().startswith("|"):
        return []
    cells = [clean_label(cell) for cell in line.strip().strip("|").split("|")]
    cells = [cell for cell in cells if cell and cell != "Item"]
    if not cells:
        return []
    if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
        return []
    return cells


def is_table_separator_line(line: str) -> bool:
    if not line.strip().startswith("|"):
        return False
    raw_cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    raw_cells = [cell for cell in raw_cells if cell]
    return bool(raw_cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in raw_cells)


def summarize_section(lines: List[str], max_items: int = 3) -> List[str]:
    out: List[str] = []

    for line in lines:
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            label = clean_label(m.group(1))
            if label and label not in out:
                out.append(label)
        m2 = re.match(r"^\s*\d+[\.)]\s+(.*)$", line)
        if m2:
            label = clean_label(m2.group(1))
            if label and label not in out:
                out.append(label)
        if len(out) >= max_items:
            return out[:max_items]

    for idx, line in enumerate(lines):
        cells = clean_table_cells(line)
        if not cells:
            continue
        if idx + 1 < len(lines) and is_table_separator_line(lines[idx + 1]):
            continue
        if len(cells) >= 2:
            label = clean_label(f"{cells[0]}: {cells[1]}")
        else:
            label = cells[0]
        if label and label not in out:
            out.append(label)
        if len(out) >= max_items:
            return out[:max_items]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "|", "```", "-", "*", "+")):
            continue
        if re.match(r"^\d+[\.)]\s+", stripped):
            continue
        if re.match(r"^-{3,}$", stripped):
            continue
        label = clean_label(stripped)
        if len(label) < 20:
            continue
        if label and label not in out:
            out.append(label)
        if len(out) >= max_items:
            return out[:max_items]

    return out[:max_items]


def parse_markdown_sections(text: str) -> Tuple[str, List[Section]]:
    title = "Diagram"
    sections: List[Section] = []
    in_code = False
    current_heading: Optional[str] = None
    current_lines: List[str] = []

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        h1 = re.match(r"^#\s+(.*)$", line)
        if h1 and title == "Diagram":
            title = clean_label(h1.group(1))
            continue

        h2 = re.match(r"^##\s+(.*)$", line)
        if h2:
            if current_heading:
                summaries = summarize_section(current_lines)
                sections.append(Section(current_heading, summaries, classify_group(current_heading)))
            current_heading = clean_label(h2.group(1))
            current_lines = []
            continue

        if current_heading:
            current_lines.append(line)

    if current_heading:
        summaries = summarize_section(current_lines)
        sections.append(Section(current_heading, summaries, classify_group(current_heading)))

    if not sections:
        fallback = summarize_section(text.splitlines(), max_items=6)
        sections = [Section("Content", fallback, "findings")]

    return title, sections


def role_for_summary(parent_role: str, summary: str) -> str:
    low = summary.lower()
    if any(k in low for k in RISK_KEYWORDS):
        return "risk"
    return parent_role


def build_flowchart_from_markdown(text: str, layout: str, max_nodes: int, palette: str) -> str:
    title, sections = parse_markdown_sections(text)

    nodes: Dict[str, Node] = {}
    edges: List[Tuple[str, str]] = []
    counter = 0

    def next_id(prefix: str = "N") -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}{counter}"

    def add_node(label: str, role: str, group: Optional[str]) -> Optional[str]:
        if len(nodes) >= max_nodes:
            return None
        node_id = next_id()
        nodes[node_id] = Node(node_id=node_id, label=clean_label(label), role=role, group=group)
        return node_id

    root_id = add_node(title, "neutral", None)
    if not root_id:
        raise ValueError("max-nodes too small to create root")

    group_hubs: Dict[str, str] = {}
    grouped_sections: Dict[str, List[Section]] = {k: [] for k in GROUP_LABELS}
    for section in sections:
        grouped_sections.setdefault(section.group, []).append(section)

    skipped_items = 0

    if layout == "grouped":
        for group in ("evidence", "findings", "decision", "implementation", "other"):
            sec_list = grouped_sections.get(group, [])
            if not sec_list:
                continue
            hub_id = add_node(GROUP_LABELS[group], GROUP_ROLE[group], group)
            if not hub_id:
                skipped_items += len(sec_list)
                continue
            group_hubs[group] = hub_id
            edges.append((root_id, hub_id))

            for sec in sec_list:
                # Avoid duplicate nodes when section heading mirrors the group label.
                target_parent = hub_id
                if sec.heading.lower() != GROUP_LABELS[group].lower():
                    sec_id = add_node(sec.heading, GROUP_ROLE[group], group)
                    if not sec_id:
                        skipped_items += 1 + len(sec.summaries)
                        continue
                    edges.append((hub_id, sec_id))
                    target_parent = sec_id
                for summary in sec.summaries:
                    role = role_for_summary(GROUP_ROLE[group], summary)
                    sum_id = add_node(summary, role, group)
                    if not sum_id:
                        skipped_items += 1
                        continue
                    edges.append((target_parent, sum_id))
    else:
        for sec in sections:
            sec_role = GROUP_ROLE.get(sec.group, "neutral")
            sec_id = add_node(sec.heading, sec_role, None)
            if not sec_id:
                skipped_items += 1 + len(sec.summaries)
                continue
            edges.append((root_id, sec_id))
            for summary in sec.summaries:
                role = role_for_summary(sec_role, summary)
                sum_id = add_node(summary, role, None)
                if not sum_id:
                    skipped_items += 1
                    continue
                edges.append((sec_id, sum_id))

    if skipped_items > 0 and len(nodes) < max_nodes:
        more_id = add_node(f"Additional items omitted: {skipped_items}", "risk", None)
        if more_id:
            edges.append((root_id, more_id))

    lines: List[str] = ["flowchart LR"]

    if layout == "grouped":
        ungrouped = [n for n in nodes.values() if n.group is None]
        for node in ungrouped:
            lines.append(f'  {node.node_id}["{node.label}"]')

        for group in ("evidence", "findings", "decision", "implementation", "other"):
            members = [n for n in nodes.values() if n.group == group]
            if not members:
                continue
            lines.append(f'  subgraph SG_{group.upper()}["{GROUP_LABELS.get(group, group.title())}"]')
            for node in members:
                lines.append(f'    {node.node_id}["{node.label}"]')
            lines.append("  end")
    else:
        for node in nodes.values():
            lines.append(f'  {node.node_id}["{node.label}"]')

    for src, dst in edges:
        lines.append(f"  {src} --> {dst}")

    if palette == "safe":
        lines.append("")
        for role, style in SAFE_CLASS_DEFS.items():
            lines.append(f"  classDef {role} {style};")

        role_map: Dict[str, List[str]] = {}
        for node in nodes.values():
            role_map.setdefault(node.role, []).append(node.node_id)

        for role in ("source", "finding", "decision", "action", "risk", "neutral"):
            members = role_map.get(role, [])
            if members:
                lines.append(f"  class {','.join(members)} {role};")

    return "\n".join(lines) + "\n"


def sanitize_mermaid_text(text: str, palette: str) -> str:
    block = extract_mermaid_block(text)
    source = block if block is not None else text

    output: List[str] = []
    node_labels: Dict[str, str] = {}

    node_pat = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)\[(.*?)\]")
    subgraph_pat = re.compile(r"^(\s*subgraph\s+)([A-Za-z_][A-Za-z0-9_-]*)(?:\[(.*)\])?\s*$")

    saw_header = False
    for raw in source.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not stripped or stripped.startswith("%%"):
            output.append(line)
            continue
        if stripped.startswith("```"):
            continue
        if stripped.startswith("classDef") or stripped.startswith("class ") or stripped.startswith("style ") or stripped.startswith("linkStyle"):
            continue

        if stripped.startswith("flowchart"):
            saw_header = True
            output.append("flowchart LR")
            continue

        sub = subgraph_pat.match(line)
        if sub:
            prefix, gid, label = sub.groups()
            if label:
                output.append(f'{prefix}{gid}["{clean_label(label)}"]')
            else:
                output.append(line)
            continue

        line = strip_markdown_links(line)
        line = strip_urls(line)

        def repl(match: re.Match[str]) -> str:
            node_id = match.group(1)
            label = clean_label(match.group(2).strip('"'))
            node_labels[node_id] = label
            return f'{node_id}["{label}"]'

        line = node_pat.sub(repl, line)
        output.append(line)

    if not saw_header:
        output.insert(0, "flowchart LR")

    if palette == "safe":
        output.append("")
        for role, style in SAFE_CLASS_DEFS.items():
            output.append(f"classDef {role} {style};")

        role_members: Dict[str, List[str]] = {k: [] for k in SAFE_CLASS_DEFS}
        for node_id, label in node_labels.items():
            low = label.lower()
            role = "neutral"
            if any(k in low for k in ("evidence", "task", "source", "probe")):
                role = "source"
            elif any(k in low for k in ("finding", "capability", "verified", "reachable")):
                role = "finding"
            elif any(k in low for k in ("decision", "recommend", "choose", "keep")):
                role = "decision"
            elif any(k in low for k in ("implement", "delta", "use ", "process", "download", "upload")):
                role = "action"
            if any(k in low for k in RISK_KEYWORDS):
                role = "risk"
            role_members[role].append(node_id)

        for role in ("source", "finding", "decision", "action", "risk", "neutral"):
            ids = role_members.get(role, [])
            if ids:
                output.append(f"class {','.join(ids)} {role};")

    return "\n".join(output).strip() + "\n"


def count_nodes(text: str) -> int:
    ids: set[str] = set()
    pat = re.compile(r'^\s*(?!subgraph\b)([A-Za-z_][A-Za-z0-9_-]*)\["', re.M)
    for match in pat.finditer(text):
        ids.add(match.group(1))
    return len(ids)


def static_validate(text: str, max_nodes: int) -> List[str]:
    errors: List[str] = []

    first_non_empty = ""
    for line in text.splitlines():
        if line.strip():
            first_non_empty = line.strip()
            break
    if not first_non_empty.startswith("flowchart"):
        errors.append("First non-empty line must start with 'flowchart'.")

    if re.search(r"\[\[[^\]]+\]\([^)]+\)\]", text):
        errors.append("Found nested markdown link labels: [[...](...)]")

    # Ensure common node-shape syntax remains balanced after sanitization.
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("classDef", "class ", "style ", "linkStyle", "%%")):
            continue
        if "[" in line or "]" in line:
            if line.count("[") != line.count("]"):
                errors.append(f"Unbalanced square brackets on line {i}")
        if '"' in line and (line.count('"') % 2 != 0):
            errors.append(f"Unbalanced double quotes on line {i}")

    for decl in UNSUPPORTED_DECLARATIONS:
        if re.search(rf"^\s*{re.escape(decl)}\b", text, flags=re.M):
            errors.append(f"Unsupported diagram declaration found: {decl}")

    node_total = count_nodes(text)
    if node_total > max_nodes:
        errors.append(f"Node count {node_total} exceeds max-nodes {max_nodes}")

    return errors


def validate_with_excalidraw_parser(text: str) -> Tuple[bool, str]:
    if not shutil.which("node"):
        return False, "error: node not found, cannot run excalidraw parser validation"

    script_dir = Path(__file__).resolve().parent
    if not (script_dir / "node_modules" / "@excalidraw" / "mermaid-to-excalidraw").exists():
        return False, "error: @excalidraw/mermaid-to-excalidraw not installed for this skill"

    js = r'''
const fs = require("fs");
const input = fs.readFileSync(0, "utf8");
(async () => {
  try {
    const { JSDOM } = require("jsdom");
    const createDOMPurify = require("dompurify");
    const dom = new JSDOM("<!doctype html><html><body></body></html>");
    global.window = dom.window;
    global.document = dom.window.document;
    global.navigator = dom.window.navigator;
    global.self = dom.window;
    global.Element = dom.window.Element;
    global.HTMLElement = dom.window.HTMLElement;
    global.SVGElement = dom.window.SVGElement;
    global.CSSStyleSheet = dom.window.CSSStyleSheet || class {
      constructor() { this.cssRules = []; }
      replaceSync() {}
      insertRule() { return 0; }
      deleteRule() {}
    };
    global.DOMPurify = createDOMPurify(dom.window);
    if (!global.SVGElement.prototype.getBBox) {
      global.SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 100, height: 24 });
    }
    if (!global.SVGElement.prototype.getComputedTextLength) {
      global.SVGElement.prototype.getComputedTextLength = () => 100;
    }
  } catch (err) {
    console.error("NODE_DOM_SETUP_FAILED: " + ((err && err.message) ? err.message : String(err)));
    process.exit(5);
  }

  let mod = null;
  try {
    mod = require("@excalidraw/mermaid-to-excalidraw");
  } catch (_) {
    try {
      mod = await import("@excalidraw/mermaid-to-excalidraw");
    } catch (_) {
      console.error("MISSING_PACKAGE");
      process.exit(3);
    }
  }
  const fn = (mod && (mod.parseMermaidToExcalidraw || (mod.default && mod.default.parseMermaidToExcalidraw)));
  if (!fn) {
    console.error("NO_PARSE_FUNCTION");
    process.exit(4);
  }
  try {
    await fn(input);
    console.log("OK");
  } catch (err) {
    console.error((err && err.message) ? err.message : String(err));
    process.exit(2);
  }
})();
'''

    proc = subprocess.run(
        ["node", "-e", js],
        input=text,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(script_dir),
    )

    if proc.returncode == 0:
        return True, "ok"
    if proc.returncode in (3, 4):
        return False, "error: @excalidraw/mermaid-to-excalidraw could not be loaded"
    return False, f"excalidraw parser validation failed: {proc.stderr.strip() or proc.stdout.strip()}"


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.max_nodes < 1:
        print("error: --max-nodes must be >= 1", file=sys.stderr)
        return 2

    text = input_path.read_text(encoding="utf-8", errors="replace")

    mode = args.mode
    if mode == "auto":
        mode = detect_input_mode(text)

    if mode == "from-markdown":
        generated = build_flowchart_from_markdown(text, layout=args.layout, max_nodes=args.max_nodes, palette=args.palette)
    else:
        generated = sanitize_mermaid_text(text, palette=args.palette)

    if args.validate in ("static", "excalidraw", "excalidraw-strict"):
        errors = static_validate(generated, args.max_nodes)
        if errors:
            for err in errors:
                print(f"error: {err}", file=sys.stderr)
            return 3

    if args.validate in ("excalidraw", "excalidraw-strict"):
        ok, msg = validate_with_excalidraw_parser(generated)
        if not ok:
            if args.validate == "excalidraw-strict":
                print(f"error: {msg}", file=sys.stderr)
                return 4
            print(f"warning: {msg}", file=sys.stderr)
            print("warning: falling back to static validation only", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
