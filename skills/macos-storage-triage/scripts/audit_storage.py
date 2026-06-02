#!/usr/bin/env python3
"""Read-only macOS storage audit for the macos-storage-triage skill."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


HOME = Path.home()


@dataclass
class Measurement:
    label: str
    path: str
    size: str
    note: str


def run(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout.strip() if exc.stdout else "", "timeout"


def du(path: Path | str, depth: int | None = None) -> str:
    p = os.fspath(path)
    if depth is None:
        code, out, err = run(["du", "-sh", p], timeout=120)
    else:
        code, out, err = run(["du", "-xhd", str(depth), p], timeout=180)
    if code != 0 or not out:
        return f"unavailable ({err or 'no output'})"
    return out


def first_size(path: Path | str) -> str:
    out = du(path)
    return out.split("\t", 1)[0] if "\t" in out else out


def collect(deep: bool = False) -> dict[str, object]:
    paths: list[tuple[str, Path | str, str]] = [
        ("user_caches", HOME / "Library/Caches", "mostly regenerable caches"),
        ("codex_home", HOME / ".codex", "agent sessions, plugins, render hosts, temp"),
        ("npm_cache", HOME / ".npm", "Node package cache and npx artifacts"),
        ("dot_cache", HOME / ".cache", "tooling caches"),
        ("pnpm_library", HOME / "Library/pnpm", "pnpm store/cache"),
        ("homebrew", "/opt/homebrew", "Homebrew prefix"),
        ("homebrew_caskroom", "/opt/homebrew/Caskroom", "Homebrew casks"),
        ("homebrew_cellar", "/opt/homebrew/Cellar", "Homebrew formulae"),
        ("core_simulator", "/System/Volumes/Data/Library/Developer/CoreSimulator", "Xcode simulator storage"),
        ("ios_simulator_assets", "/System/Volumes/Data/System/Library/AssetsV2/com_apple_MobileAsset_iOSSimulatorRuntime", "iOS simulator mobile assets"),
        ("xros_simulator_assets", "/System/Volumes/Data/System/Library/AssetsV2/com_apple_MobileAsset_xrOSSimulatorRuntime", "xrOS simulator mobile assets"),
        ("vm", "/System/Volumes/VM", "swap/kernelcore; do not manually delete"),
    ]

    if deep:
        paths = [
            ("home", HOME, "user-owned data and app state"),
            ("applications", "/Applications", "installed applications"),
            ("user_library", HOME / "Library", "user-level app/developer state"),
            ("application_support", HOME / "Library/Application Support", "mixed app cache and app state"),
        ] + paths

    measurements = [
        Measurement(label, os.fspath(path), first_size(path), note)
        for label, path, note in paths
    ]

    df_code, df_out, df_err = run(["df", "-h", "/System/Volumes/Data", "/"])
    snap_code, snap_out, snap_err = run(["tmutil", "listlocalsnapshots", "/"])
    sim_code, sim_out, sim_err = run(["xcrun", "simctl", "runtime", "list"])
    brew_code, brew_out, brew_err = run(["brew", "cleanup", "-n"], timeout=120)

    return {
        "df": df_out or df_err,
        "local_snapshots": snap_out or snap_err,
        "measurements": [asdict(item) for item in measurements],
        "simctl_runtime_list": sim_out or sim_err,
        "brew_cleanup_dry_run": brew_out or brew_err,
    }


def print_markdown(data: dict[str, object]) -> None:
    print("# macOS Storage Audit")
    print()
    print("## Free Space")
    print()
    print("```text")
    print(data["df"])
    print("```")
    print()
    print("## Targeted Measurements")
    print()
    print("| Label | Size | Path | Note |")
    print("|---|---:|---|---|")
    for item in data["measurements"]:
        print(f"| {item['label']} | {item['size']} | `{item['path']}` | {item['note']} |")
    print()
    print("## Local Snapshots")
    print()
    print("```text")
    print(data["local_snapshots"])
    print("```")
    print()
    print("## Simulator Runtimes")
    print()
    print("```text")
    print(data["simctl_runtime_list"])
    print("```")
    print()
    print("## Homebrew Cleanup Dry Run")
    print()
    print("```text")
    print(data["brew_cleanup_dry_run"])
    print("```")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--markdown", action="store_true", help="Emit Markdown. Default.")
    parser.add_argument("--deep", action="store_true", help="Include broad, slower top-level measurements.")
    args = parser.parse_args()

    data = collect(deep=args.deep)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_markdown(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
