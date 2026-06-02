#!/usr/bin/env python3
"""Build a minimal evidence-index.json from probe and frame manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str) -> dict:
    resolved = Path(path).expanduser()
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"JSON file not found: {resolved}") from exc
    except PermissionError as exc:
        raise SystemExit(f"JSON file is not readable: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {resolved} at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"JSON file must contain an object: {resolved}")
    return data


def require_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise SystemExit(f"{field} must be numeric.")
    return float(value)


def validate_probe(probe: dict) -> float:
    if not isinstance(probe.get("source"), str) or not probe["source"]:
        raise SystemExit("probe.source is required.")
    duration = require_number(probe.get("duration_seconds"), "probe.duration_seconds")
    if duration <= 0:
        raise SystemExit("probe.duration_seconds must be positive.")
    return duration


def validate_frames_manifest(frames_manifest: dict, duration: float) -> list[dict]:
    frames = frames_manifest.get("frames")
    if not isinstance(frames, list):
        raise SystemExit("frames manifest must contain a frames list.")
    if not frames:
        raise SystemExit("Frame manifest contains no frames.")

    for index, frame in enumerate(frames, start=1):
        if not isinstance(frame, dict):
            raise SystemExit(f"frames[{index}] must be an object.")
        frame_id = frame.get("id", f"frames[{index}]")
        if not isinstance(frame.get("id"), str) or not frame["id"]:
            raise SystemExit(f"{frame_id} missing required field id.")
        t_start = require_number(frame.get("t_start"), f"frame {frame_id}.t_start")
        t_end = require_number(frame.get("t_end"), f"frame {frame_id}.t_end")
        if not t_start < t_end:
            raise SystemExit(f"frame {frame_id} must satisfy t_start < t_end.")
        if not (0 <= t_start <= duration and 0 <= t_end <= duration):
            raise SystemExit(
                f"frame {frame_id} is outside duration: t_start={t_start}, t_end={t_end}, duration={duration}."
            )
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", required=True, help="JSON from probe_video.py.")
    parser.add_argument("--frames", required=True, help="frames-manifest.json.")
    parser.add_argument("--out", default="vision-in-time-output/evidence-index.json")
    parser.add_argument("--feedback", default=None, help="Optional feedback text for this pass.")
    args = parser.parse_args()

    probe = load(args.probe)
    frames_manifest = load(args.frames)
    duration = validate_probe(probe)
    frames = validate_frames_manifest(frames_manifest, duration)

    candidate_moments = [
        {
            "id": f"cm_{i:03d}",
            "t_start": frame["t_start"],
            "t_end": frame["t_end"],
            "reason": "initial_sparse_sample",
            "evidence_ids": [frame["id"]],
            "rank": i,
        }
        for i, frame in enumerate(frames, start=1)
    ]

    index = {
        "video": {
            "source": probe["source"],
            "duration_seconds": probe["duration_seconds"],
            "width": probe.get("width"),
            "height": probe.get("height"),
            "fps": probe.get("fps"),
            "has_audio": bool(probe.get("has_audio")),
        },
        "frames": frames,
        "candidate_moments": candidate_moments,
        "observations": [],
        "uncertainties": [
            {
                "id": "unc_001",
                "text": "Initial index has sampled evidence but no agent observations yet.",
                "evidence_ids": [],
            }
        ],
        "feedback": [
            {
                "kind": "user_feedback",
                "text": args.feedback,
                "target": None,
                "suggested_window": None,
                "priority": "medium",
            }
        ]
        if args.feedback is not None and args.feedback.strip()
        else [],
    }

    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
