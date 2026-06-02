#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from typing import Optional


SKIP_DIRS = {".git", ".next", ".turbo", "node_modules", "dist", "build", "out"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that a route uses local Shadcn UI when available.")
    parser.add_argument("--cwd", default=".", help="Workspace directory.")
    parser.add_argument("--route-file", required=True, help="Route file to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    route_file = Path(args.route_file).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    evidence: dict = {}

    if not cwd.exists() or not cwd.is_dir():
        errors.append(f"Unreadable cwd: {cwd}")
        return emit(args.json, errors, warnings, evidence)

    if not route_file.exists() or not route_file.is_file():
        errors.append(f"Route file does not exist: {route_file}")
        return emit(args.json, errors, warnings, evidence)

    try:
        route_file.relative_to(cwd)
    except ValueError:
        warnings.append("Route file is outside cwd; local app evidence may not apply.")

    parts = route_file.parts
    if "app" not in parts or route_file.name not in {"page.tsx", "page.jsx"}:
        errors.append("Route file should be an App Router page such as app/<slug>/page.tsx.")

    text = route_file.read_text(encoding="utf-8")
    shadcn_evidence = detect_shadcn(cwd)
    evidence.update(shadcn_evidence)
    waivers = collect_waivers(text)
    evidence["waivers"] = waivers

    ui_imports = re.findall(
        r"""from\s+["'][^"']*(?:@/components/ui|components/ui|/components/ui)/([^"']+)["']""",
        text,
    )
    evidence["ui_imports"] = sorted(set(ui_imports))

    if shadcn_evidence["has_shadcn"] and not ui_imports:
        errors.append("Shadcn is detected in this repo, but the route imports no components from components/ui.")

    if "<!doctype" in text.lower() or re.search(r"<(?:html|head|body)\b", text, re.IGNORECASE):
        errors.append("Route appears to include standalone HTML document boilerplate.")

    if re.search(r"<style\b", text, re.IGNORECASE):
        warnings.append("Route includes a raw <style> block; prefer Tailwind and local UI primitives.")

    if "dangerouslySetInnerHTML" in text:
        warnings.append("Route uses dangerouslySetInnerHTML; verify this is necessary and safe.")

    if re.search(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]", text):
        errors.append("Found emoji-like characters; this skill forbids emojis in code or UI.")

    warnings.extend(find_shadcn_rule_violations(text, shadcn_evidence, waivers))

    route_slug = infer_route_slug(route_file)
    evidence["route_slug"] = route_slug

    return emit(args.json, errors, warnings, evidence)


def detect_shadcn(root: Path) -> dict:
    components_json = find_files(root, "components.json", 5)
    components_ui = find_components_ui(root, 6)
    installed_components = installed_components_from_dirs(components_ui)
    return {
        "components_json": [str(item) for item in components_json],
        "components_ui_dirs": [str(item) for item in components_ui],
        "installed_components": installed_components,
        "has_shadcn": bool(components_json and components_ui),
    }


def installed_components_from_dirs(components_ui_dirs: list[Path]) -> list[str]:
    components: set[str] = set()
    for directory in components_ui_dirs:
        if not directory.exists():
            continue
        for child in directory.iterdir():
            if child.is_file() and child.suffix in {".tsx", ".jsx"}:
                components.add(child.stem)
    return sorted(components)


def collect_waivers(text: str) -> dict:
    waivers: dict = {}
    pattern = re.compile(
        r"(?:intent-html-renderer-waive|shadcn-waive)\s+([a-z0-9-_, ]+)\s*:\s*([^\n*}]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        codes = [code.strip().lower() for code in match.group(1).split(",")]
        reason = match.group(2).strip()
        for code in codes:
            if code:
                waivers[code] = reason
    return waivers


def find_shadcn_rule_violations(text: str, shadcn_evidence: dict, waivers: dict) -> list[str]:
    warnings: list[str] = []
    installed = set(shadcn_evidence.get("installed_components") or [])

    def add_warning(code: str, message: str) -> None:
        if code in waivers:
            return
        warnings.append(f"[{code}] {message}")

    raw_color_matches = sorted(
        set(
            re.findall(
                r"\b(?:bg|text|border|ring)-(?:red|green|blue|emerald|violet|purple|yellow|orange|amber|sky|cyan|teal|lime|rose|pink|indigo)-\d{2,3}\b",
                text,
            )
        )
    )
    if raw_color_matches:
        add_warning(
            "raw-color",
            "Route uses raw Tailwind color utilities; prefer Shadcn semantic tokens or component variants: "
            + ", ".join(raw_color_matches[:8]),
        )

    if re.search(r"\bspace-[xy]-\d", text):
        add_warning("spacing", "Route uses space-x-* or space-y-*; Shadcn guidance prefers flex/grid with gap-*.")

    if re.search(r"\bdark:(?:bg|text|border|ring)-", text):
        add_warning("dark-color", "Route uses manual dark: color overrides; prefer semantic tokens that already adapt to dark mode.")

    if "table" in installed and re.search(r"<table\b", text):
        add_warning("raw-table", "Route uses raw <table>; use components/ui/table primitives when Shadcn Table is installed.")

    if "separator" in installed and (re.search(r"<hr\b", text) or "border-t" in text):
        add_warning("separator", "Route appears to use raw separators; prefer the Shadcn Separator component where practical.")

    if "skeleton" in installed and "animate-pulse" in text:
        add_warning("skeleton", "Route uses custom animate-pulse loading markup; prefer the Shadcn Skeleton component.")

    if "empty" in installed and re.search(
        r"\bNo (?:results|items|records|posts|projects|matches|data)(?:[ .:-]+(?:found|yet|available))?\b",
        text,
        re.IGNORECASE,
    ):
        add_warning("empty-state", "Route contains an empty-state phrase; consider using the Shadcn Empty component.")

    for warning in find_button_icon_warnings(text):
        add_warning("button-icon", warning)

    if "<Button" in text and re.search(r"<Button\b[^>]*(?:isPending|isLoading)=", text):
        add_warning("button-loading", "Button has isPending/isLoading props; Shadcn buttons should compose Spinner plus disabled state.")

    if "<Card" in text and "<CardHeader" not in text:
        add_warning("card-composition", "Route uses Card without CardHeader; prefer full Shadcn Card composition.")

    if "<TabsTrigger" in text and "<TabsList" not in text:
        add_warning("tabs-list", "Route uses TabsTrigger without TabsList; triggers must be nested in TabsList.")

    overlay_requirements = [
        ("DialogContent", "DialogTitle"),
        ("SheetContent", "SheetTitle"),
        ("DrawerContent", "DrawerTitle"),
    ]
    for content_name, title_name in overlay_requirements:
        if f"<{content_name}" in text and f"<{title_name}" not in text:
            add_warning("overlay-title", f"Route uses {content_name} without {title_name}; overlays need titles for accessibility.")

    grouped_items = [
        ("SelectItem", "SelectGroup"),
        ("DropdownMenuItem", "DropdownMenuGroup"),
        ("MenubarItem", "MenubarGroup"),
        ("ContextMenuItem", "ContextMenuGroup"),
        ("CommandItem", "CommandGroup"),
    ]
    for item_name, group_name in grouped_items:
        if f"<{item_name}" in text and f"<{group_name}" not in text:
            add_warning("grouped-items", f"Route uses {item_name} without {group_name}; Shadcn item components should live inside their group.")

    if "<form" in text and "field" in installed and "<FieldGroup" not in text:
        add_warning("field-group", "Route contains a form without FieldGroup; use Shadcn FieldGroup and Field for form layout.")

    if "<InputGroup" in text and "<Input " in text:
        add_warning("input-group", "Route uses raw Input inside InputGroup; use InputGroupInput or InputGroupTextarea.")

    if looks_like_default_neutral_shadcn(text, installed):
        add_warning(
            "visual-treatment",
            "Route appears to use default-neutral Shadcn without explicit visual treatment. Use semantic/chart tokens, component variants, route-local color-mix() accents, or add a waiver when the user explicitly asked for plain styling.",
        )

    return dedupe(warnings)


def looks_like_default_neutral_shadcn(text: str, installed: set[str]) -> bool:
    if not installed:
        return False

    shadcn_surface = sum(
        token in text
        for token in (
            "<Card",
            "<Button",
            "<Badge",
            "<Table",
            "<Tabs",
            "<Alert",
            "<Progress",
            "<Sheet",
            "<Dialog",
            "<Field",
            "<InputGroup",
        )
    )
    if shadcn_surface < 3:
        return False

    visual_treatment_markers = (
        "var(--chart-",
        "color-mix(",
        "--status-",
        "--lane-",
        "--metric-",
        "bg-[",
        "text-[",
        "border-[",
        "[&_[data-slot=progress-indicator]]",
    )
    return not any(marker in text for marker in visual_treatment_markers)


def find_button_icon_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", text)
    for block in button_blocks:
        icon_tags = re.findall(r"<[A-Z][A-Za-z0-9]*Icon\b[^>]*>", block)
        for icon_tag in icon_tags:
            if "data-icon=" not in icon_tag:
                warnings.append("Button icon is missing data-icon; use data-icon=\"inline-start\" or \"inline-end\".")
            if re.search(r'className=["\'][^"\']*(?:\bsize-\d|\bw-\d|\bh-\d|\bmr-\d|\bml-\d)', icon_tag):
                warnings.append("Button icon uses sizing or margin classes; Shadcn button icons should rely on data-icon styling.")
    return dedupe(warnings)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


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


def infer_route_slug(route_file: Path) -> Optional[str]:
    parts = list(route_file.parts)
    if "app" not in parts:
        return None
    index = parts.index("app")
    route_parts = parts[index + 1 : -1]
    if not route_parts:
        return "/"
    return "/" + "/".join(route_parts)


def emit(as_json: bool, errors: list[str], warnings: list[str], evidence: dict) -> int:
    result = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "evidence": evidence,
    }
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if errors:
            print("Shadcn route validation failed:")
            for error in errors:
                print(f"- {error}")
        else:
            print("Shadcn route validation passed.")
        for warning in warnings:
            print(f"Warning: {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
