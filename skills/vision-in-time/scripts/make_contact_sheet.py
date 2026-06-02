#!/usr/bin/env python3
"""Create a contact sheet from sampled frames."""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames_dir")
    parser.add_argument("--out", default="vision-in-time-output/contact-sheet.jpg")
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=360)
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required.")

    frames_dir = Path(args.frames_dir).expanduser().resolve()
    frames = sorted(frames_dir.glob("*.jpg"))
    if not frames:
        raise SystemExit(f"No .jpg frames found in {frames_dir}")
    if args.cols <= 0:
        raise SystemExit("--cols must be greater than 0.")

    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = math.ceil(len(frames) / args.cols)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        list_path = Path(handle.name)
        for frame in frames:
            escaped = str(frame).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-vf",
            f"scale={args.thumb_width}:-1,tile={args.cols}x{rows}",
            "-frames:v",
            "1",
            str(out),
        ]
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "ffmpeg failed to create contact sheet.") from exc
    finally:
        list_path.unlink(missing_ok=True)

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
