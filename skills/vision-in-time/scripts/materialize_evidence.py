#!/usr/bin/env python3
"""Materialize a frame or clip around an evidence window."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "ffmpeg failed.") from exc


def fmt(seconds: float) -> str:
    return f"{seconds:.3f}".rstrip("0").rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--out-dir", default="vision-in-time-output/materialized")
    parser.add_argument("--clip", action="store_true", help="Write a clip instead of a single frame.")
    parser.add_argument("--pad", type=float, default=1.0, help="Seconds around evidence window.")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required.")

    index = json.loads(Path(args.index).expanduser().read_text(encoding="utf-8"))
    pointers = index.get("frames", []) + index.get("candidate_moments", [])
    pointer = next((item for item in pointers if item.get("id") == args.evidence_id), None)
    if not pointer:
        raise SystemExit(f"Evidence id not found: {args.evidence_id}")

    source = Path(pointer.get("source") or index["video"]["source"]).expanduser().resolve()
    start = max(0.0, float(pointer.get("t_start", 0.0)) - args.pad)
    end = min(float(index["video"]["duration_seconds"]), float(pointer.get("t_end", start)) + args.pad)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clip:
        out = out_dir / f"{args.evidence_id}_{fmt(start)}-{fmt(end)}.mp4"
        run(["ffmpeg", "-y", "-ss", fmt(start), "-to", fmt(end), "-i", str(source), "-c", "copy", str(out)])
    else:
        t = float(pointer.get("t_start", start))
        out = out_dir / f"{args.evidence_id}_{fmt(t)}s.jpg"
        run(["ffmpeg", "-y", "-ss", fmt(t), "-i", str(source), "-frames:v", "1", "-q:v", "2", str(out)])

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
