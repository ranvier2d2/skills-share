#!/usr/bin/env python3
"""Sample frames from a video and write a frame manifest."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise SystemExit("ffmpeg is required but was not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "ffmpeg failed.") from exc


def duration_seconds(video: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("ffprobe is required but was not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "ffprobe failed to read video duration.") from exc
    raw = result.stdout.strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise SystemExit(f"ffprobe returned a non-numeric duration: {raw!r}") from exc


def fmt_time(seconds: float) -> str:
    return f"{seconds:.3f}".rstrip("0").rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--out-dir", default="vision-in-time-output/frames")
    parser.add_argument("--every", type=float, default=5.0, help="Seconds between samples.")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=None)
    parser.add_argument("--width", type=int, default=1280)
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required.")

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = duration_seconds(video)
    end = min(args.end if args.end is not None else duration, duration)
    if end >= duration:
        end = max(args.start, duration - 0.001)
    if args.every <= 0:
        raise SystemExit("--every must be greater than 0.")
    if args.start < 0 or args.start > end:
        raise SystemExit("--start must be within the video bounds.")

    times: list[float] = []
    current = args.start
    while current <= end + 1e-6:
        times.append(round(current, 3))
        current += args.every
    if not times:
        times.append(round(end, 3))

    frames = []
    digits = max(4, int(math.log10(max(len(times), 1))) + 1)
    for index, t in enumerate(times):
        frame_path = out_dir / f"frame_{index:0{digits}d}_{fmt_time(t)}s.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                fmt_time(t),
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={args.width}:-1",
                "-q:v",
                "2",
                str(frame_path),
            ]
        )
        frames.append(
            {
                "id": f"frame_{index:0{digits}d}",
                "type": "frame",
                "source": str(video),
                "t_start": t,
                "t_end": t,
                "path": str(frame_path),
                "reason": "uniform_sample",
            }
        )

    manifest = {
        "video": str(video),
        "duration_seconds": duration,
        "sample_every_seconds": args.every,
        "frames": frames,
    }
    manifest_path = out_dir.parent / "frames-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
