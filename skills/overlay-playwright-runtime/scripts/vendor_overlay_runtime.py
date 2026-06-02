#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "runtime"
DEFAULT_MANIFEST_RELATIVE_PATH = Path(".codex") / "overlay-playwright-runtime" / "vendor-manifest.json"
FILES_TO_COPY = (
    ("a11y-overlay.js", "a11y-overlay.js"),
    ("playwright/overlay-client.mjs", "playwright/overlay-client.mjs"),
)


@dataclass(frozen=True)
class SourceFile:
    source_path: Path
    target_relative_path: Path
    source_sha256: str


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for vendoring the a11y-overlay runtime and Playwright client into a target repository.
    
    Recognized options:
    - --target-root: Absolute path to the target repository root (required).
    - --force: Overwrite existing target files that differ from the bundled assets.
    - --dry-run: Print planned operations without performing copy or delete actions.
    - --temporary: Record copied files in a manifest for later cleanup.
    - --cleanup: Remove files previously recorded in a manifest, preserving any that were modified since vendoring.
    - --manifest-path: Override the manifest file location; defaults to the repository-relative path defined by DEFAULT_MANIFEST_RELATIVE_PATH.
    
    Returns:
        argparse.Namespace: Parsed arguments with attributes
        `target_root` (str), `force` (bool), `dry_run` (bool), `temporary` (bool),
        `cleanup` (bool), and `manifest_path` (str | None).
    """
    parser = argparse.ArgumentParser(
        description="Vendor the a11y-overlay runtime and Playwright client into another repo."
    )
    parser.add_argument(
        "--target-root",
        required=True,
        help="Absolute path to the target repository root."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files that differ from the bundled assets."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without copying or deleting files."
    )
    parser.add_argument(
        "--temporary",
        action="store_true",
        help="Record copied files in a manifest so they can be cleaned up after an audit-only run."
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove files previously copied with --temporary, preserving any that changed since vendoring."
    )
    parser.add_argument(
        "--manifest-path",
        help=(
            "Override the vendoring manifest path. Defaults to "
            f"{DEFAULT_MANIFEST_RELATIVE_PATH.as_posix()} inside the target root."
        ),
    )
    return parser.parse_args()


def sha256_for_path(path: Path) -> str:
    """
    Compute the SHA-256 hex digest of a file's contents.
    
    Parameters:
        path (Path): Path to the file to hash.
    
    Returns:
        str: SHA-256 digest of the file contents as a lowercase hexadecimal string.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for_args(target_root: Path, args: argparse.Namespace) -> Path:
    """
    Determine the filesystem path to the vendor manifest based on CLI arguments and the target root.
    
    If `args.manifest_path` is provided, expand user (`~`) and resolve that path. Otherwise return the resolved path obtained by joining `target_root` with `DEFAULT_MANIFEST_RELATIVE_PATH`.
    
    Parameters:
        target_root (Path): Resolved path to the target repository root; used when no manifest override is supplied.
        args (argparse.Namespace): Parsed CLI arguments; may contain a `manifest_path` string to override the default.
    
    Returns:
        Path: Resolved filesystem path to the manifest file.
    """
    if args.manifest_path:
        return Path(args.manifest_path).expanduser().resolve()
    return (target_root / DEFAULT_MANIFEST_RELATIVE_PATH).resolve()


def ensure_source_files(asset_root: Path) -> list[SourceFile]:
    """
    Resolve and validate bundled asset files under `asset_root` and return their metadata.
    
    Parameters:
    	asset_root (Path): Directory containing the bundled runtime assets referenced by FILES_TO_COPY.
    
    Returns:
    	list[SourceFile]: A list of SourceFile records for each required asset. Each record contains the resolved `source_path`, the `target_relative_path` where the file should be placed in the target repository, and the computed `source_sha256` of the source file.
    
    Raises:
    	FileNotFoundError: If one or more required source files are missing; the exception message lists the missing paths.
    """
    resolved: list[SourceFile] = []
    missing: list[str] = []

    for source_rel, target_rel in FILES_TO_COPY:
        source_path = asset_root / source_rel
        if not source_path.exists():
            missing.append(str(source_path))
            continue
        resolved.append(
            SourceFile(
                source_path=source_path,
                target_relative_path=Path(target_rel),
                source_sha256=sha256_for_path(source_path),
            )
        )

    if missing:
        joined = "\n".join(missing)
        raise FileNotFoundError(f"missing source files:\n{joined}")

    return resolved


def prune_empty_parents(start: Path, stop_at: Path, dry_run: bool) -> None:
    """
    Remove empty parent directories starting at `start`, walking upward until reaching `stop_at` (exclusive) or the filesystem root.
    
    Stops walking when a directory exists and contains any entries. For each directory that is empty and removable, prints an action message; when `dry_run` is true it only prints the first planned removal and does not perform any filesystem changes.
    
    Parameters:
    	start (Path): Directory to start checking for emptiness.
    	stop_at (Path): Directory at which to stop walking; `stop_at` itself will not be removed.
    	dry_run (bool): If true, only print the removal that would be performed and do not actually remove directories.
    """
    current = start
    while current != stop_at and current != current.parent:
        if current.exists() and any(current.iterdir()):
            break
        print(f"{'would remove empty dir' if dry_run else 'remove empty dir'} {current}")
        if dry_run:
            break
        current.rmdir()
        current = current.parent


def load_manifest(manifest_path: Path) -> dict:
    """
    Load and parse a JSON manifest from the given filesystem path.
    
    Parameters:
        manifest_path (Path): Path to the manifest file to read.
    
    Returns:
        dict: The parsed JSON manifest.
    
    Raises:
        FileNotFoundError: If `manifest_path` does not exist.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text("utf8"))


def write_manifest(manifest_path: Path, payload: dict, dry_run: bool) -> None:
    """
    Write the manifest payload to the given path, creating parent directories as needed.
    
    The payload is written as pretty-printed JSON with a trailing newline using UTF-8 encoding. If `dry_run` is True, the function only prints the planned action and does not modify the filesystem.
    
    Parameters:
        manifest_path (Path): Destination file path for the manifest.
        payload (dict): JSON-serializable manifest content to write.
        dry_run (bool): If True, do not write the file; only print what would be done.
    """
    print(f"{'would write' if dry_run else 'write'} manifest {manifest_path}")
    if dry_run:
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", "utf8")


def run_cleanup(target_root: Path, manifest_path: Path, dry_run: bool) -> int:
    """
    Remove files recorded in a vendoring manifest and, when all recorded files match the recorded checksums, remove the manifest.
    
    Loads the manifest at manifest_path, verifies its "targetRoot" matches target_root, and then iterates the manifest's `copied` entries. For each recorded file, if the file is missing it is skipped; if the file's SHA-256 differs from the recorded `sha256` the file is preserved and retained in the updated manifest; if the SHA-256 matches the recorded value the file is deleted (or reported as deleted when `dry_run` is True) and empty parent directories are pruned up to target_root. If any files are preserved, the manifest is updated to list only the preserved entries. If no preserved files remain, the manifest itself is deleted (or reported as deleted when `dry_run` is True) and parent directories above the manifest are pruned.
    
    Parameters:
        target_root (Path): Resolved path to the target repository root referenced by the manifest.
        manifest_path (Path): Path to the manifest file produced by a previous vendoring run.
        dry_run (bool): If True, report actions without making filesystem changes.
    
    Returns:
        int: Exit code indicating the result:
            0 - Cleanup completed (or simulated) either fully or partially (preserved files left in manifest).
            5 - Manifest file not found at manifest_path.
            6 - Manifest's recorded targetRoot does not match the provided target_root.
    """
    try:
        manifest = load_manifest(manifest_path)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 5

    if str(target_root) != manifest.get("targetRoot"):
        print(
            "error: manifest target root does not match the requested target root:\n"
            f"  manifest: {manifest.get('targetRoot')}\n"
            f"  target:   {target_root}",
            file=sys.stderr,
        )
        return 6

    remaining: list[dict] = []
    removed = 0

    for record in manifest.get("copied", []):
        relative_path = Path(record["path"])
        target_path = target_root / relative_path
        expected_sha = record["sha256"]

        if not target_path.exists():
            print(f"skip missing {target_path}")
            continue

        if sha256_for_path(target_path) != expected_sha:
            print(f"preserve modified {target_path}")
            remaining.append(record)
            continue

        print(f"{'would remove' if dry_run else 'remove'} {target_path}")
        if not dry_run:
            target_path.unlink()
            prune_empty_parents(target_path.parent, target_root, dry_run=False)
        removed += 1

    if remaining:
        manifest["copied"] = remaining
        write_manifest(manifest_path, manifest, dry_run)
        print(f"cleanup incomplete: preserved {len(remaining)} modified file(s)")
        return 0

    print(f"{'would remove' if dry_run else 'remove'} manifest {manifest_path}")
    if not dry_run and manifest_path.exists():
        manifest_path.unlink()
        prune_empty_parents(manifest_path.parent, target_root, dry_run=False)

    print(f"cleanup complete: removed {removed} file(s)")
    return 0


def main() -> int:
    """
    Execute the CLI to vendor bundled overlay runtime files into a target repository or to perform manifest-driven cleanup.
    
    This function parses CLI arguments, validates modes and the target root, and then either:
    - runs cleanup when `--cleanup` is specified (delegates to `run_cleanup` and returns its exit code), or
    - vendors bundled assets into `--target-root`, comparing SHA-256 digests to decide whether to reuse, report conflicts, or overwrite when `--force` is used; it can record copied files in a manifest when `--temporary` is set and simulate actions with `--dry-run`.
    
    Returns:
        int: Process exit code:
            - `0` on successful vendoring or completed cleanup (or when no changes are necessary).
            - `2` for invalid argument combinations or when the target root is missing or not a directory.
            - `3` if required source asset files are missing.
            - `4` when existing target files differ from bundled assets and `--force` was not supplied.
            - When `--cleanup` is used, the function returns the exit code produced by `run_cleanup` (which may be `5`, `6`, or `0` depending on manifest loading and verification outcomes).
    """
    args = parse_args()
    if args.cleanup and args.force:
      print("error: --cleanup cannot be combined with --force", file=sys.stderr)
      return 2
    if args.cleanup and args.temporary:
      print("error: choose either --temporary or --cleanup, not both", file=sys.stderr)
      return 2
    if args.temporary and args.force:
      print("error: --temporary cannot be combined with --force", file=sys.stderr)
      return 2

    asset_root = DEFAULT_ASSET_ROOT.resolve()
    target_root = Path(args.target_root).expanduser().resolve()
    manifest_path = manifest_path_for_args(target_root, args)

    if not target_root.exists():
        print(f"error: target root does not exist: {target_root}", file=sys.stderr)
        return 2
    if not target_root.is_dir():
        print(f"error: target root is not a directory: {target_root}", file=sys.stderr)
        return 2

    if args.cleanup:
        return run_cleanup(target_root, manifest_path, args.dry_run)

    try:
        source_files = ensure_source_files(asset_root)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3

    conflicts: list[Path] = []
    planned_copies: list[tuple[SourceFile, Path]] = []
    copied_records: list[dict] = []
    reused: list[Path] = []

    for source in source_files:
        target_path = target_root / source.target_relative_path
        if target_path.exists():
            target_sha = sha256_for_path(target_path)
            if target_sha == source.source_sha256:
                reused.append(target_path)
                print(f"reuse compatible {target_path}")
                continue
            if not args.force:
                conflicts.append(target_path)
                continue
        planned_copies.append((source, target_path))

    if conflicts:
        joined = "\n".join(str(path) for path in conflicts)
        print(
            "error: target files differ from the bundled assets. Re-run with --force to overwrite:\n"
            f"{joined}",
            file=sys.stderr,
        )
        return 4

    for source, target_path in planned_copies:
        print(f"{'would copy' if args.dry_run else 'copy'} {source.source_path} -> {target_path}")
        copied_records.append({
            "path": source.target_relative_path.as_posix(),
            "sha256": source.source_sha256,
        })
        if args.dry_run:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source.source_path, target_path)

    if args.temporary:
        payload = {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "targetRoot": str(target_root),
            "copied": copied_records,
            "reused": [path.relative_to(target_root).as_posix() for path in reused],
        }
        write_manifest(manifest_path, payload, args.dry_run)

    if args.dry_run:
        print("dry run complete")
    elif copied_records:
        print("overlay runtime vendored successfully")
    else:
        print("overlay runtime already compatible; nothing copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
