#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_SANDBOX_ROOT = Path.home() / ".codex" / "overlay-playwright-runtime" / "sandbox"
DEFAULT_ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "sandbox"
DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parent.parent / "assets" / "runtime" / "playwright"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the dedicated Playwright sandbox used by overlay-playwright-runtime operate mode."
    )
    parser.add_argument(
        "--sandbox-root",
        default=str(DEFAULT_SANDBOX_ROOT),
        help="Sandbox directory to create or refresh. Defaults to ~/.codex/overlay-playwright-runtime/sandbox."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Copy assets but skip npm install."
    )
    parser.add_argument(
        "--skip-browser-install",
        action="store_true",
        help="Skip installing Chromium with Playwright."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Kept for compatibility; sandbox helper files are refreshed in place by default."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned operations without changing the filesystem."
    )
    return parser.parse_args()


def iter_asset_files(asset_root: Path) -> list[tuple[Path, Path]]:
    if not asset_root.exists():
        raise FileNotFoundError(f"missing sandbox asset root: {asset_root}")

    pairs: list[tuple[Path, Path]] = []
    for source_path in sorted(asset_root.rglob("*")):
        if source_path.is_file():
            pairs.append((source_path, source_path.relative_to(asset_root)))
    if not pairs:
        raise FileNotFoundError(f"no sandbox assets found under: {asset_root}")
    return pairs


def iter_runtime_client_files(runtime_root: Path) -> list[tuple[Path, Path]]:
    expected = [
        "../a11y-overlay.js",
    ]
    pairs: list[tuple[Path, Path]] = []
    for name in expected:
        source_path = (runtime_root / name).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"missing runtime client asset: {source_path}")
        relative_path = Path(name).name
        pairs.append((source_path, Path(relative_path)))
    return pairs


def copy_assets(asset_root: Path, runtime_root: Path, sandbox_root: Path, dry_run: bool) -> int:
    pairs = iter_asset_files(asset_root)
    pairs.extend(iter_runtime_client_files(runtime_root))

    for source_path, relative_path in pairs:
        target_path = sandbox_root / relative_path
        print(f"{'would copy' if dry_run else 'copy'} {source_path} -> {target_path}")
        if dry_run:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    return 0


def run_command(args: list[str], cwd: Path, dry_run: bool) -> None:
    print(f"{'would run' if dry_run else 'run'} {' '.join(args)} (cwd={cwd})")
    if dry_run:
        return
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    args = parse_args()
    asset_root = DEFAULT_ASSET_ROOT.resolve()
    runtime_root = DEFAULT_RUNTIME_ROOT.resolve()
    sandbox_root = Path(args.sandbox_root).expanduser().resolve()

    try:
        if not args.dry_run:
            sandbox_root.mkdir(parents=True, exist_ok=True)
        copy_status = copy_assets(asset_root, runtime_root, sandbox_root, args.dry_run)
        if copy_status:
            return copy_status
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3

    if args.skip_install:
        if args.dry_run:
            print("dry run complete")
        else:
            print("sandbox helper files copied; npm install skipped")
        return 0

    package_json = sandbox_root / "package.json"
    if not package_json.exists() and not args.dry_run:
        print(f"error: package.json not found after copying assets: {package_json}", file=sys.stderr)
        return 5

    try:
        run_command(["npm", "install"], sandbox_root, args.dry_run)
        if not args.skip_browser_install:
            run_command(["npx", "playwright", "install", "chromium"], sandbox_root, args.dry_run)
    except FileNotFoundError as error:
        print(f"error: missing command: {error}", file=sys.stderr)
        return 6
    except subprocess.CalledProcessError as error:
        print(f"error: command failed with exit code {error.returncode}", file=sys.stderr)
        return error.returncode

    if args.dry_run:
        print("dry run complete")
    else:
        print(f"operate sandbox ready at {sandbox_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
