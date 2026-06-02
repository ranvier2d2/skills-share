#!/usr/bin/env python3
"""Probe video metadata with ffprobe and write normalized JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def run_json(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise SystemExit("ffprobe is required but was not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.strip() or "ffprobe failed.") from exc
    return json.loads(result.stdout)


def fps_from_stream(stream: dict) -> float | None:
    value = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not value or value == "0/0":
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to the video file.")
    parser.add_argument("--out", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    if not shutil.which("ffprobe"):
        raise SystemExit("ffprobe is required but was not found on PATH.")

    raw = run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ]
    )
    streams = raw.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    duration = (
        video_stream.get("duration")
        or raw.get("format", {}).get("duration")
        or 0
    )

    normalized = {
        "source": str(video),
        "duration_seconds": float(duration),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": fps_from_stream(video_stream),
        "has_audio": bool(audio_streams),
        "format": raw.get("format", {}).get("format_name"),
        "streams": [
            {
                "index": s.get("index"),
                "type": s.get("codec_type"),
                "codec": s.get("codec_name"),
                "duration_seconds": float(s["duration"]) if s.get("duration") else None,
            }
            for s in streams
        ],
    }

    text = json.dumps(normalized, indent=2)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
