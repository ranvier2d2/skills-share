#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Optional


SKIP_DIRS = {".git", ".next", ".turbo", "node_modules", "dist", "build", "out"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Shadcn project context from local files when the Shadcn CLI is unavailable."
    )
    parser.add_argument("--cwd", default=".", help="Workspace or app directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. Plain mode prints a short summary.")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        result = {"ok": False, "error": f"Unreadable cwd: {cwd}"}
        emit(result, args.json)
        return 2

    result = collect_context(cwd)
    emit(result, args.json)
    return 0 if result["ok"] else 1


def collect_context(cwd: Path) -> dict:
    package_jsons = find_files(cwd, "package.json", max_depth=4)
    components_jsons = find_files(cwd, "components.json", max_depth=5)
    components_ui_dirs = find_components_ui(cwd, max_depth=6)
    tsconfigs = find_files(cwd, "tsconfig.json", max_depth=4)

    packages = [read_json(path) for path in package_jsons]
    configs = [read_json(path) for path in components_jsons]
    tsconfig_data = [read_json(path) for path in tsconfigs]

    installed_components = sorted(
        {
            child.stem
            for directory in components_ui_dirs
            if directory.exists()
            for child in directory.iterdir()
            if child.is_file() and child.suffix in {".tsx", ".jsx"}
        }
    )

    package_manager = first_string(pkg.get("packageManager") for pkg in packages)
    dependencies = merge_dependencies(packages)
    first_config = next((config for config in configs if isinstance(config, dict)), {})
    aliases = first_config.get("aliases") if isinstance(first_config, dict) else {}
    tailwind = first_config.get("tailwind") if isinstance(first_config, dict) else {}

    result = {
        "ok": True,
        "cwd": str(cwd),
        "source": "local-files",
        "packageManager": package_manager,
        "framework": infer_framework(dependencies),
        "componentsJson": [str(path) for path in components_jsons],
        "componentsUiDirs": [str(path) for path in components_ui_dirs],
        "installedComponents": installed_components,
        "componentCount": len(installed_components),
        "style": first_config.get("style") if isinstance(first_config, dict) else None,
        "base": first_config.get("base") if isinstance(first_config, dict) else None,
        "iconLibrary": first_config.get("iconLibrary") if isinstance(first_config, dict) else None,
        "tailwindCss": tailwind.get("css") if isinstance(tailwind, dict) else None,
        "tailwindBaseColor": tailwind.get("baseColor") if isinstance(tailwind, dict) else None,
        "tailwindCssVariables": tailwind.get("cssVariables") if isinstance(tailwind, dict) else None,
        "aliases": aliases if isinstance(aliases, dict) else {},
        "tsconfigPaths": collect_tsconfig_paths(tsconfig_data),
        "dependencies": dependencies,
        "warnings": [],
    }

    if not components_jsons:
        result["warnings"].append("No components.json found.")
    if not components_ui_dirs:
        result["warnings"].append("No components/ui directory found.")
    if not installed_components:
        result["warnings"].append("No installed Shadcn component files detected.")

    return result


def infer_framework(dependencies: dict) -> Optional[str]:
    if "next" in dependencies:
        return "next"
    if "react" in dependencies:
        return "react"
    return None


def collect_tsconfig_paths(tsconfig_data: list[dict]) -> dict:
    paths: dict = {}
    for data in tsconfig_data:
        compiler_options = data.get("compilerOptions") if isinstance(data, dict) else {}
        current_paths = compiler_options.get("paths") if isinstance(compiler_options, dict) else {}
        if isinstance(current_paths, dict):
            paths.update(current_paths)
    return paths


def merge_dependencies(packages: list[dict]) -> dict:
    merged: dict = {}
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps = pkg.get(key)
            if isinstance(deps, dict):
                merged.update(deps)
    return merged


def first_string(values) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            return value
    return None


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def find_files(root: Path, name: str, max_depth: int) -> list[Path]:
    matches: list[Path] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if depth(root, current_path) > max_depth:
            dirs[:] = []
            continue
        if name in files:
            matches.append(current_path / name)
    return sorted(matches)


def find_components_ui(root: Path, max_depth: int) -> list[Path]:
    matches: list[Path] = []
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if depth(root, current_path) > max_depth:
            dirs[:] = []
            continue
        if current_path.name == "components" and "ui" in dirs:
            matches.append(current_path / "ui")
    return sorted(matches)


def depth(root: Path, current: Path) -> float:
    try:
        return len(current.relative_to(root).parts)
    except ValueError:
        # Paths outside the root should sort beyond any bounded traversal depth.
        return float("inf")


def emit(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if not result.get("ok"):
        print(result.get("error", "Unable to extract Shadcn context."))
        return
    print(f"Framework: {result.get('framework')}")
    print(f"Style: {result.get('style')}")
    print(f"Icon library: {result.get('iconLibrary')}")
    print(f"Installed components: {result.get('componentCount')}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")


if __name__ == "__main__":
    raise SystemExit(main())
