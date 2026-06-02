#!/usr/bin/env python3
"""Validate a Vision In Time evidence index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_time(name: str, value: object, duration: float, errors: list[str]) -> None:
    require(isinstance(value, (int, float)), f"{name} must be numeric.", errors)
    if isinstance(value, (int, float)):
        require(0 <= float(value) <= duration, f"{name}={value} is outside duration {duration}.", errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index")
    args = parser.parse_args()

    index_path = Path(args.index).expanduser().resolve()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    video = data.get("video", {})
    duration = video.get("duration_seconds")
    require(isinstance(duration, (int, float)) and duration > 0, "video.duration_seconds must be positive.", errors)
    duration_value = float(duration or 0)

    evidence_by_id = {}
    for section in ("frames", "candidate_moments"):
        last_t = -1.0
        for item in data.get(section, []):
            item_id = item.get("id")
            require(isinstance(item_id, str) and item_id, f"{section} item missing id.", errors)
            if item_id:
                require(item_id not in evidence_by_id, f"Duplicate evidence id: {item_id}", errors)
                evidence_by_id[item_id] = item
            t_start = item.get("t_start")
            t_end = item.get("t_end")
            check_time(f"{section}.{item_id}.t_start", t_start, duration_value, errors)
            check_time(f"{section}.{item_id}.t_end", t_end, duration_value, errors)
            if isinstance(t_start, (int, float)) and isinstance(t_end, (int, float)):
                require(t_start < t_end, f"{section}.{item_id} must satisfy t_start < t_end.", errors)
                require(t_start >= last_t, f"{section} is not monotonic at {item_id}.", errors)
                last_t = float(t_start)

    for obs in data.get("observations", []):
        obs_id = obs.get("id", "<missing>")
        check_time(f"observation.{obs_id}.t", obs.get("t"), duration_value, errors)
        for evidence_id in obs.get("evidence_ids", []):
            require(evidence_id in evidence_by_id, f"Observation {obs_id} references missing evidence id {evidence_id}.", errors)

    for uncertainty in data.get("uncertainties", []):
        uncertainty_id = uncertainty.get("id", "<missing>")
        require(bool(uncertainty.get("text")), f"Uncertainty {uncertainty_id} needs text.", errors)
        evidence_ids = uncertainty.get("evidence_ids")
        require(isinstance(evidence_ids, list), f"Uncertainty {uncertainty_id} needs evidence_ids list.", errors)

    feedback_kinds = {"missed_moment", "correction", "clarification", "user_feedback"}
    feedback_priorities = {"low", "medium", "high"}
    for item in data.get("feedback", []):
        feedback_id = item.get("kind", "<missing>") if isinstance(item, dict) else "<invalid>"
        require(isinstance(item, dict), "Feedback item must be an object.", errors)
        if not isinstance(item, dict):
            continue
        require(item.get("kind") in feedback_kinds, f"Feedback {feedback_id} has invalid kind.", errors)
        require(isinstance(item.get("text"), str) and bool(item["text"].strip()), f"Feedback {feedback_id} needs text.", errors)
        require(item.get("priority") in feedback_priorities, f"Feedback {feedback_id} has invalid priority.", errors)
        suggested_window = item.get("suggested_window")
        if suggested_window is not None:
            require(isinstance(suggested_window, dict), f"Feedback {feedback_id}.suggested_window must be object or null.", errors)
            if isinstance(suggested_window, dict):
                t_start = suggested_window.get("t_start")
                t_end = suggested_window.get("t_end")
                check_time(f"feedback.{feedback_id}.suggested_window.t_start", t_start, duration_value, errors)
                check_time(f"feedback.{feedback_id}.suggested_window.t_end", t_end, duration_value, errors)
                if isinstance(t_start, (int, float)) and isinstance(t_end, (int, float)):
                    require(t_start < t_end, f"Feedback {feedback_id}.suggested_window must satisfy t_start < t_end.", errors)

    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        return 1

    print(json.dumps({"valid": True, "evidence_count": len(evidence_by_id)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
