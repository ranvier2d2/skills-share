#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Optional


SKIP_DIRS = {
    ".git",
    ".next",
    ".turbo",
    "node_modules",
    "dist",
    "build",
    "out",
}

DEFAULT_GLOBAL_SHADCN_HOST = Path.home() / ".codex" / "render-hosts" / "intent-html-renderer-shadcn"

RELEVANT_DEPS = {
    "next",
    "react",
    "react-dom",
    "@json-render/core",
    "@json-render/react",
    "@jsonrender/core",
    "@jsonrender/react",
    "lucide-react",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect the strongest UI render target for an intent-driven artifact.")
    parser.add_argument("--cwd", default=".", help="Workspace directory to inspect.")
    parser.add_argument("--intent", default="", help="Optional user intent text. Explicit portable-file requests override app detection.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        result = {
            "ok": False,
            "recommended_target": None,
            "evidence": {},
            "warnings": [f"Unreadable cwd: {cwd}"],
            "required_validation": [],
        }
        emit(result, args.json)
        return 2

    evidence = collect_evidence(cwd)
    evidence["global_shadcn_host"] = collect_global_host_evidence()
    intent_overrides = classify_intent_overrides(args.intent)
    recommended_target, required_validation, warnings = recommend_target(evidence, intent_overrides)
    result = {
        "ok": True,
        "cwd": str(cwd),
        "recommended_target": recommended_target,
        "intent_overrides": intent_overrides,
        "evidence": evidence,
        "warnings": warnings,
        "required_validation": required_validation,
    }
    emit(result, args.json)
    return 0


def collect_evidence(cwd: Path) -> dict:
    package_jsons = find_files(cwd, "package.json", max_depth=4)
    components_json = find_files(cwd, "components.json", max_depth=5)
    shadcn_catalog = find_files(cwd, "shadcn-catalog.ts", max_depth=6)
    shadcn_registry = find_files(cwd, "shadcn-registry.tsx", max_depth=6)
    app_dirs = find_dirs(cwd, "app", max_depth=5)
    components_ui_dirs = find_components_ui(cwd, max_depth=6)
    html_files = find_files(cwd, "index.html", max_depth=3)

    dependencies = {}
    for package_json in package_jsons:
        dependencies[str(package_json)] = read_package_dependencies(package_json)

    has_next = any("next" in deps for deps in dependencies.values())
    has_react = any("react" in deps for deps in dependencies.values())
    has_json_render = any(
        "@json-render/core" in deps
        or "@json-render/react" in deps
        or "@jsonrender/core" in deps
        or "@jsonrender/react" in deps
        for deps in dependencies.values()
    )

    return {
        "package_jsons": paths(package_jsons),
        "app_dirs": paths(app_dirs),
        "components_json": paths(components_json),
        "components_ui_dirs": paths(components_ui_dirs),
        "shadcn_catalog": paths(shadcn_catalog),
        "shadcn_registry": paths(shadcn_registry),
        "index_html": paths(html_files),
        "has_next": has_next,
        "has_react": has_react,
        "has_json_render": has_json_render,
        "dependencies": dependencies,
    }


def collect_global_host_evidence() -> dict:
    host = DEFAULT_GLOBAL_SHADCN_HOST
    package_json = host / "package.json"
    app_dir = host / "app"
    components_json = host / "components.json"
    components_ui = host / "components" / "ui"
    node_modules = host / "node_modules"
    return {
        "path": str(host),
        "exists": host.exists(),
        "package_json": str(package_json) if package_json.exists() else None,
        "app_dir": str(app_dir) if app_dir.exists() else None,
        "components_json": str(components_json) if components_json.exists() else None,
        "components_ui": str(components_ui) if components_ui.exists() else None,
        "node_modules": str(node_modules) if node_modules.exists() else None,
        "ready": all(
            [
                package_json.exists(),
                app_dir.exists(),
                components_json.exists(),
                components_ui.exists(),
                node_modules.exists(),
            ]
        ),
    }


def classify_intent_overrides(intent: str) -> dict:
    normalized = " ".join(intent.lower().split())
    portable_terms = [
        "portable html",
        "standalone html",
        "single html",
        "single-file html",
        "self-contained html",
        "send to a teammate",
        "send to teammate",
        "open as a file",
        "html file",
    ]
    return {
        "explicit_portable_html": bool(normalized and any(term in normalized for term in portable_terms)),
    }


def recommend_target(evidence: dict, intent_overrides: Optional[dict] = None) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    intent_overrides = intent_overrides or {}
    has_shadcn = bool(evidence["components_json"] and evidence["components_ui_dirs"])
    has_json_catalog = bool(evidence["shadcn_catalog"] and evidence["shadcn_registry"])
    has_next_route = bool(evidence["has_next"] and evidence["app_dirs"])
    global_host = evidence.get("global_shadcn_host") or {}

    if intent_overrides.get("explicit_portable_html"):
        warnings.append("Explicit portable HTML request overrides detected app/Shadcn targets.")
        return (
            "standalone-html",
            ["scripts/validate_html_artifact.py <artifact.html> --strict", "desktop and mobile browser proof"],
            warnings,
        )

    if has_next_route and has_shadcn:
        validation = [
            "scripts/validate_shadcn_route.py --cwd <repo> --route-file <route>",
            "project type-check/build command",
            "desktop and mobile browser proof",
        ]
        if has_json_catalog:
            validation.insert(
                1,
                "scripts/validate_ui_tree.py <tree.json> --catalog <shadcn-catalog.ts> --registry <shadcn-registry.tsx> when saving UI trees",
            )
        return "next-shadcn-route", validation, warnings

    if has_json_catalog:
        return (
            "json-render-ui-tree-or-preview",
            [
                "scripts/validate_ui_tree.py <tree.json> --catalog <shadcn-catalog.ts> --registry <shadcn-registry.tsx>",
                "project type-check/build command",
                "preview browser proof",
            ],
            warnings,
        )

    if global_host.get("ready"):
        if has_next_route or evidence["has_react"]:
            warnings.append("React/Next detected without Shadcn evidence; using global Shadcn render host for artifact output.")
        else:
            warnings.append("No local app UI system detected; using global Shadcn render host instead of standalone HTML.")
        return (
            "global-shadcn-render-host",
            [
                "scripts/ensure_global_shadcn_host.py --json",
                "write route under ~/.codex/render-hosts/intent-html-renderer-shadcn/app/artifacts/<slug>/page.tsx",
                "validate_shadcn_route.py --cwd ~/.codex/render-hosts/intent-html-renderer-shadcn --route-file <host-route>",
                "host pnpm type-check/build",
                "desktop and mobile browser proof",
            ],
            warnings,
        )

    if has_next_route or evidence["has_react"]:
        warnings.append("React/Next detected without Shadcn evidence and global Shadcn host is not ready; use existing app components if present.")
        return (
            "react-app-route-or-component",
            ["project type-check/build command", "desktop and mobile browser proof"],
            warnings,
        )

    warnings.append("Global Shadcn render host is not ready; run ensure_global_shadcn_host.py --install before falling back to standalone HTML.")

    if evidence["index_html"]:
        warnings.append("Static HTML context detected; standalone HTML is acceptable if no app target exists.")
    else:
        warnings.append("No local app UI system detected; standalone HTML is the fallback target.")
    return (
        "standalone-html",
        ["scripts/validate_html_artifact.py <artifact.html> --strict", "desktop and mobile browser proof"],
        warnings,
    )


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


def find_dirs(root: Path, name: str, max_depth: int) -> list[Path]:
    matches: list[Path] = []
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if depth(root, current_path) > max_depth:
            dirs[:] = []
            continue
        for directory in dirs:
            if directory == name:
                matches.append(current_path / directory)
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


def read_package_dependencies(package_json: Path) -> dict:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    merged = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = data.get(key)
        if isinstance(value, dict):
            for package, version in value.items():
                if package in RELEVANT_DEPS:
                    merged[package] = version
    return merged


def depth(root: Path, current: Path) -> float:
    try:
        return len(current.relative_to(root).parts)
    except ValueError:
        # Paths outside the root should sort beyond any bounded traversal depth.
        return float("inf")


def paths(items: list[Path]) -> list[str]:
    return [str(item) for item in items]


def emit(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"Recommended target: {result.get('recommended_target')}")
    for key, value in result.get("evidence", {}).items():
        if key == "dependencies":
            continue
        print(f"{key}: {value}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")


if __name__ == "__main__":
    raise SystemExit(main())
