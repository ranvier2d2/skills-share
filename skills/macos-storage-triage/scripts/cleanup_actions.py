#!/usr/bin/env python3
"""Confirmed cleanup actions for the macos-storage-triage skill."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ACTIONS = {
    "brew-cleanup": "Run `brew cleanup` after showing `brew cleanup -n`.",
    "simctl-delete-unavailable": "Delete unavailable simulators via `xcrun simctl delete unavailable`.",
    "simctl-remove-dyld-caches": "Remove simulator dyld shared caches via `xcrun simctl runtime dyld_shared_cache remove --all`.",
    "simctl-delete-all-runtimes": "Delete all simulator runtime disk images via `xcrun simctl runtime delete all`.",
    "remove-miniconda-cask": "Remove Homebrew miniconda cask; tries brew first, optional direct fallback for user-owned residue.",
}


def homebrew_prefixes() -> list[Path]:
    prefixes: list[Path] = []
    brew = resolve_tool("brew")
    proc = subprocess.run([brew, "--prefix"], text=True, capture_output=True, check=False) if brew else None

    if proc and proc.returncode == 0 and proc.stdout.strip():
        prefixes.append(Path(proc.stdout.strip()))

    for candidate in [Path("/opt/homebrew"), Path("/usr/local")]:
        if candidate not in prefixes:
            prefixes.append(candidate)
    return prefixes


def resolve_tool(name: str) -> str | None:
    return shutil.which(name)


def miniconda_paths() -> list[Path]:
    return [prefix / "Caskroom" / "miniconda" for prefix in homebrew_prefixes()]


def conda_links() -> list[Path]:
    links: list[Path] = []
    for prefix in homebrew_prefixes():
        links.extend([prefix / "bin" / "conda", prefix / "bin" / "conda-env"])
    return links


def run(cmd: list[str], dry_run: bool = False) -> int:
    exe = resolve_tool(cmd[0])
    if not exe:
        print(f"Required tool not found on PATH: {cmd[0]}", file=sys.stderr)
        return 127
    resolved = [exe, *cmd[1:]]
    print("+ " + " ".join(resolved))
    if dry_run:
        return 0
    return subprocess.call(resolved)


def call_capture(cmd: list[str]) -> tuple[int, str]:
    exe = resolve_tool(cmd[0])
    if not exe:
        message = f"Required tool not found on PATH: {cmd[0]}"
        print(message, file=sys.stderr)
        return 127, message
    resolved = [exe, *cmd[1:]]
    print("+ " + " ".join(resolved))
    proc = subprocess.run(resolved, text=True, capture_output=True, check=False)
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
    if output:
        print(output)
    return proc.returncode, output


def require_confirm(action: str, confirm: str | None) -> None:
    if confirm != action:
        print(f"Refusing destructive action. Re-run with --confirm {action}", file=sys.stderr)
        raise SystemExit(2)


def list_actions() -> None:
    for name, description in ACTIONS.items():
        print(f"{name}: {description}")


def action_brew_cleanup(dry_run: bool) -> int:
    if dry_run:
        return run(["brew", "cleanup", "-n"], dry_run=False)
    return run(["brew", "cleanup"], dry_run=False)


def action_simctl_delete_unavailable(dry_run: bool) -> int:
    if dry_run:
        print("No dry-run exists for this action; command would be:")
        return run(["xcrun", "simctl", "delete", "unavailable"], dry_run=True)
    return run(["xcrun", "simctl", "delete", "unavailable"])


def action_simctl_remove_dyld(dry_run: bool) -> int:
    if dry_run:
        print("No dry-run exists for this action; command would be:")
        return run(["xcrun", "simctl", "runtime", "dyld_shared_cache", "remove", "--all"], dry_run=True)
    return run(["xcrun", "simctl", "runtime", "dyld_shared_cache", "remove", "--all"])


def action_simctl_delete_all_runtimes(dry_run: bool) -> int:
    if dry_run:
        code, output = call_capture(["xcrun", "simctl", "runtime", "delete", "all", "--dry-run"])
        if code != 0 and "No matching images found to delete" in output:
            return 0
        return code
    return run(["xcrun", "simctl", "runtime", "delete", "all"])


def action_remove_miniconda(dry_run: bool, direct_fallback: bool) -> int:
    paths = miniconda_paths()
    links = conda_links()
    managed_roots = [path.resolve(strict=False) for path in paths]

    if dry_run:
        print("Would try: brew uninstall --cask miniconda")
        for path in paths:
            print(f"Fallback candidate: {path}")
        for link in links:
            print(f"Fallback symlink candidate: {link}")
        return 0

    code = run(["brew", "uninstall", "--cask", "miniconda"])
    if code == 0:
        return 0

    if not direct_fallback:
        print("Homebrew uninstall failed. Direct fallback not enabled.", file=sys.stderr)
        print("Inspect ownership and re-run with --direct-fallback only after user confirmation.", file=sys.stderr)
        return code

    for path in paths:
        if path.exists():
            print(f"+ rm -rf {path}")
            shutil.rmtree(path)
    for link in links:
        if not link.is_symlink():
            continue
        target = link.resolve(strict=False)
        if not any(target == root or root in target.parents for root in managed_roots):
            print(f"Skipping non-miniconda link: {link} -> {target}", file=sys.stderr)
            continue
        print(f"+ rm -f {link}")
        link.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List available actions.")
    parser.add_argument("--action", choices=sorted(ACTIONS), help="Action to run.")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned action where supported.")
    parser.add_argument("--confirm", help="Must equal the action name for destructive runs.")
    parser.add_argument("--direct-fallback", action="store_true", help="Allow direct miniconda residue removal if brew fails.")
    args = parser.parse_args()

    if args.list or not args.action:
        list_actions()
        return 0

    if not args.dry_run:
        require_confirm(args.action, args.confirm)

    if args.action == "brew-cleanup":
        return action_brew_cleanup(args.dry_run)
    if args.action == "simctl-delete-unavailable":
        return action_simctl_delete_unavailable(args.dry_run)
    if args.action == "simctl-remove-dyld-caches":
        return action_simctl_remove_dyld(args.dry_run)
    if args.action == "simctl-delete-all-runtimes":
        return action_simctl_delete_all_runtimes(args.dry_run)
    if args.action == "remove-miniconda-cask":
        return action_remove_miniconda(args.dry_run, args.direct_fallback)

    raise RuntimeError(f"Unhandled action {args.action!r} in main(): ensure ACTIONS has a corresponding handler.")


if __name__ == "__main__":
    raise SystemExit(main())
