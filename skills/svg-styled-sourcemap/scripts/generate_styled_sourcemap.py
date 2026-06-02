#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+")
BULLET_RE = re.compile(r"^[ \t]*([-*+]|(\d+\.))\s+")


@dataclass(frozen=True)
class InputDoc:
    label: str
    content: str


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _first_nonempty_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        if line.strip():
            return line
    return None


def _drop_first_heading(text: str) -> str:
    # Drop only when the *first non-empty* line is a heading. This avoids
    # duplicating file titles when we add our own "## <file>" section.
    lines = text.splitlines()
    first_i = None
    for i, line in enumerate(lines):
        if line.strip():
            first_i = i
            break
    if first_i is None:
        return text
    if HEADING_RE.match(lines[first_i]):
        return "\n".join(lines[:first_i] + lines[first_i + 1 :]) + "\n"
    return text


def _shift_headings(text: str, *, offset: int) -> str:
    if offset <= 0:
        return text

    out: List[str] = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if not m:
            out.append(line)
            continue
        hashes = m.group("hashes")
        new_level = min(6, len(hashes) + offset)
        out.append("#" * new_level + line[m.end() - 1 :])  # keep the space + rest
    return "\n".join(out) + "\n"


def _filter_outline_lines(text: str) -> str:
    out: List[str] = []
    for line in text.splitlines():
        if HEADING_RE.match(line) or BULLET_RE.match(line):
            out.append(line.rstrip("\n"))
    return "\n".join(out) + "\n"


def build_combined_markdown(
    inputs: List[InputDoc],
    *,
    root_label: str,
    include_root_heading: bool,
    filter_outline: bool,
    drop_first_heading: bool,
    heading_offset: int,
) -> str:
    parts: List[str] = []

    if include_root_heading:
        parts.append(f"# {root_label}")
        parts.append("")

    for input_doc in inputs:
        parts.append(f"## {input_doc.label}")
        parts.append("")

        body = input_doc.content
        if drop_first_heading:
            body = _drop_first_heading(body)
        body = _shift_headings(body, offset=heading_offset)
        if filter_outline:
            body = _filter_outline_lines(body)

        parts.append(body.rstrip("\n"))
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def _script_path(script_name: str) -> Path:
    here = Path(__file__).resolve()
    return here.parent / script_name


def _run(argv: List[str]) -> None:
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout.strip() or f"Command failed: {' '.join(argv)}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a styled SVG sourcemap from one or more Markdown files (or stdin)."
    )

    p.add_argument(
        "--in",
        dest="in_paths",
        action="append",
        required=True,
        help="Input Markdown path. Repeatable. Use '-' for stdin (at most once).",
    )
    p.add_argument("--out", dest="out_styled", required=True, help="Output styled SVG path.")
    p.add_argument(
        "--out-base",
        dest="out_base",
        default=None,
        help="Optional output path for the base (un-styled) SVG.",
    )

    p.add_argument("--title", default="SVG Sourcemap", help="Top-left title text (also default root label).")
    p.add_argument("--root-label", default=None, help="Root heading label in the outline (defaults to --title).")

    p.add_argument("--node-width", type=int, default=340)
    p.add_argument("--h-gap", type=int, default=140)
    p.add_argument("--v-gap", type=int, default=12)
    p.add_argument("--grid-size", type=int, default=80)
    p.add_argument("--font-size", type=int, default=12)
    p.add_argument("--font-family", default="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial")
    p.add_argument("--pad-x", type=int, default=14)
    p.add_argument("--pad-y", type=int, default=10)
    p.add_argument("--margin", type=int, default=60)
    p.add_argument("--tab-width", type=int, default=2)
    p.add_argument("--indent-size", type=int, default=2)
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument("--no-js", action="store_true")

    p.add_argument(
        "--style-preset",
        default="kimojo-sourcemap",
        help="Style preset name from assets/presets (default: kimojo-sourcemap).",
    )
    p.add_argument(
        "--style-css",
        default=None,
        help="Additional CSS file path to inject (in addition to --style-preset).",
    )
    p.add_argument("--no-background", action="store_true", help="Do not inject background rect.")
    p.add_argument("--no-ensure-ids", action="store_true", help="Do not add ids to elements.")
    p.add_argument("--no-add-classes", action="store_true", help="Do not add svg-el/svg-<tag> classes.")
    p.add_argument("--no-ensure-titles", action="store_true", help="Do not add <title> tooltips.")

    p.add_argument(
        "--keep-all-lines",
        action="store_true",
        help="Keep non-heading/non-bullet lines (default filters to headings + bullets).",
    )
    p.add_argument(
        "--keep-first-heading",
        action="store_true",
        help="Keep the first heading of each input file (default drops it to avoid duplicates).",
    )
    p.add_argument(
        "--no-root-heading",
        action="store_true",
        help="Do not add a synthetic root heading.",
    )
    p.add_argument(
        "--heading-offset",
        type=int,
        default=2,
        help="Heading level offset applied to each input file's headings (default: 2).",
    )

    return p


def main(argv: List[str]) -> int:
    args = build_arg_parser().parse_args(argv)

    in_paths: List[str] = args.in_paths
    if in_paths.count("-") > 1:
        raise SystemExit("Use '-' (stdin) at most once.")

    inputs: List[InputDoc] = []
    for in_path in in_paths:
        label = "stdin" if in_path == "-" else in_path
        content = _read_text(in_path)
        inputs.append(InputDoc(label=label, content=content))

    root_label = args.root_label or args.title
    combined = build_combined_markdown(
        inputs,
        root_label=root_label,
        include_root_heading=not args.no_root_heading,
        filter_outline=not args.keep_all_lines,
        drop_first_heading=not args.keep_first_heading,
        heading_offset=args.heading_offset,
    )

    out_styled = Path(args.out_styled).expanduser().resolve()
    out_styled.parent.mkdir(parents=True, exist_ok=True)

    out_base: Optional[Path]
    temp_base_path: Optional[Path] = None
    if args.out_base:
        out_base = Path(args.out_base).expanduser().resolve()
        out_base.parent.mkdir(parents=True, exist_ok=True)
    else:
        fd, temp_path = tempfile.mkstemp(prefix=".sourcemap_base_", suffix=".svg", dir=str(out_styled.parent))
        os.close(fd)
        temp_base_path = Path(temp_path)
        out_base = temp_base_path

    generator = _script_path("generate_svg_sourcemap.py")
    enhancer = _script_path("svg_css_enhance.py")

    gen_cmd: List[str] = [
        sys.executable,
        str(generator),
        "--in",
        "-",
        "--out",
        str(out_base),
        "--title",
        args.title,
        "--node-width",
        str(args.node_width),
        "--h-gap",
        str(args.h_gap),
        "--v-gap",
        str(args.v_gap),
        "--grid-size",
        str(args.grid_size),
        "--font-size",
        str(args.font_size),
        "--font-family",
        args.font_family,
        "--pad-x",
        str(args.pad_x),
        "--pad-y",
        str(args.pad_y),
        "--margin",
        str(args.margin),
        "--tab-width",
        str(args.tab_width),
        "--indent-size",
        str(args.indent_size),
    ]
    if args.max_depth is not None:
        gen_cmd += ["--max-depth", str(args.max_depth)]
    if args.no_js:
        gen_cmd.append("--no-js")

    proc = subprocess.run(gen_cmd, input=combined, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(proc.stdout.strip() or "SVG generation failed.")

    enh_cmd: List[str] = [
        sys.executable,
        str(enhancer),
        "--in",
        str(out_base),
        "--out",
        str(out_styled),
        "--preset",
        args.style_preset,
    ]

    if args.style_css:
        enh_cmd += ["--css", args.style_css]

    if not args.no_ensure_ids:
        enh_cmd += ["--ensure-ids", "--id-prefix", "sourcemap"]
    if not args.no_add_classes:
        enh_cmd.append("--add-classes")
    if not args.no_ensure_titles:
        enh_cmd.append("--ensure-titles")
    if not args.no_background:
        enh_cmd.append("--add-background")

    _run(enh_cmd)

    if temp_base_path is not None:
        try:
            temp_base_path.unlink(missing_ok=True)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

