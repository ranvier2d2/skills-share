#!/usr/bin/env python3
"""Render PDF files to deterministic PNG page set."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from common import ensure_dir, upsert_stage, write_json


PDF_EXT = ".pdf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render PDF files to PNG pages.")
    parser.add_argument("--input", required=True, help="PDF file or directory containing PDFs")
    parser.add_argument("--case-id", required=True, help="Case identifier")
    parser.add_argument("--out", required=True, help="Case output base directory")
    parser.add_argument("--dpi", type=int, default=220, help="Render DPI")
    parser.add_argument("--page-range", default=None, help="Optional range as start:end")
    return parser.parse_args()


def list_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.lower() == PDF_EXT:
        return [input_path.resolve()]
    if input_path.is_dir():
        return sorted([p.resolve() for p in input_path.glob("*.pdf")])
    return []


def parse_page_range(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    match = re.match(r"^(\d+):(\d+)$", raw.strip())
    if not match:
        raise ValueError("--page-range must be start:end, e.g. 1:10")
    start = int(match.group(1))
    end = int(match.group(2))
    if start < 1 or end < start:
        raise ValueError("Invalid --page-range boundaries")
    return start, end


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    out_base = Path(args.out).expanduser().resolve()

    if shutil.which("pdftoppm") is None:
        raise SystemExit("pdftoppm is required but not found in PATH.")

    pdfs = list_pdfs(input_path)
    if not pdfs:
        raise SystemExit(f"No PDFs found at {input_path}")

    start_page, end_page = parse_page_range(args.page_range)

    raw_dir = out_base / "pages" / "raw"
    ensure_dir(raw_dir)
    temp_dir = out_base / "tmp" / "render"
    ensure_dir(temp_dir)

    manifest_pages: list[dict] = []

    for idx, pdf_path in enumerate(pdfs, start=1):
        doc_id = f"doc{idx:02d}"
        prefix = temp_dir / f"{doc_id}_tmp"

        cmd = ["pdftoppm", "-png", "-r", str(args.dpi)]
        if start_page is not None:
            cmd.extend(["-f", str(start_page)])
        if end_page is not None:
            cmd.extend(["-l", str(end_page)])
        cmd.extend([str(pdf_path), str(prefix)])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"pdftoppm failed for {pdf_path}: {proc.stderr.strip()}")

        temp_pages = sorted(temp_dir.glob(f"{doc_id}_tmp-*.png"))
        if not temp_pages:
            continue

        for page_idx, temp_png in enumerate(temp_pages, start=1):
            filename = f"{doc_id}_page{page_idx:04d}.png"
            target = raw_dir / filename
            temp_png.replace(target)
            manifest_pages.append(
                {
                    "page_id": target.stem,
                    "filename": target.name,
                    "source_pdf": str(pdf_path),
                    "source_page": page_idx,
                    "doc_id": doc_id,
                    "dpi": args.dpi,
                }
            )

    for leftover in temp_dir.glob("*.png"):
        leftover.unlink(missing_ok=True)

    render_manifest = {
        "case_id": args.case_id,
        "source": str(input_path),
        "pdf_count": len(pdfs),
        "page_count": len(manifest_pages),
        "pages": manifest_pages,
    }
    write_json(out_base / "pages" / "raw" / "render_manifest.json", render_manifest)

    upsert_stage(
        out_base,
        "render",
        {
            "pdf_count": len(pdfs),
            "page_count": len(manifest_pages),
            "raw_dir": str(raw_dir),
        },
    )

    print(f"Rendered {len(manifest_pages)} page(s) from {len(pdfs)} PDF(s) into {raw_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
