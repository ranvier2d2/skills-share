#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a flat UI tree JSON file.")
    parser.add_argument("tree_file", type=Path)
    parser.add_argument("--catalog", type=Path, help="Optional TypeScript catalog file.")
    parser.add_argument("--registry", type=Path, help="Optional TypeScript registry file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    evidence: dict = {}

    try:
        tree = json.loads(args.tree_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Failed to read file: {args.tree_file}")
        return emit(args.json, errors, warnings, evidence)
    except OSError as error:
        errors.append(f"Failed to read file {args.tree_file}: {error}")
        return emit(args.json, errors, warnings, evidence)
    except json.JSONDecodeError as error:
        errors.append(f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}")
        return emit(args.json, errors, warnings, evidence)

    catalog = extract_catalog(args.catalog, errors, warnings) if args.catalog else None
    registry = extract_registry(args.registry, errors, warnings) if args.registry else None
    if catalog:
        evidence["catalog_components"] = sorted(catalog["components"])
        evidence["catalog_children"] = sorted(catalog["has_children"])
    if registry:
        evidence["registry_components"] = sorted(registry)

    element_map = validate_shape(tree, errors)
    validate_component_types(element_map, catalog, registry, errors, warnings)

    return emit(args.json, errors, warnings, evidence)


def validate_shape(tree: object, errors: list[str]) -> dict:
    if not isinstance(tree, dict):
        errors.append("Tree must be an object.")
        return {}

    root = tree.get("root")
    elements = tree.get("elements")

    if not isinstance(root, str) or not root:
        errors.append("root must be a non-empty string.")

    if isinstance(elements, list):
        element_map = {item.get("key"): item for item in elements if isinstance(item, dict)}
    elif isinstance(elements, dict):
        element_map = elements
    else:
        errors.append("elements must be an array or object.")
        element_map = {}

    if root and root not in element_map:
        errors.append(f"root key not found in elements: {root}")

    for key, element in element_map.items():
        if not isinstance(key, str) or not key:
            errors.append("Every element needs a non-empty string key.")
            continue
        if not isinstance(element, dict):
            errors.append(f"{key}: element must be an object.")
            continue
        if not isinstance(element.get("type"), str) or not element.get("type"):
            errors.append(f"{key}: missing type string.")
        if not isinstance(element.get("props"), dict):
            errors.append(f"{key}: props must be an object.")
        children = element.get("children")
        if children is None:
            errors.append(f"{key}: children must be an array, even if empty.")
            continue
        if not isinstance(children, list):
            errors.append(f"{key}: children must be an array.")
            continue
        for child in children:
            if child not in element_map:
                errors.append(f"{key}: child key not found: {child}")

    return element_map


def validate_component_types(
    element_map: dict,
    catalog: Optional[dict],
    registry: Optional[set[str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    for key, element in element_map.items():
        if not isinstance(element, dict):
            continue
        component_type = element.get("type")
        if not isinstance(component_type, str):
            continue

        if catalog and component_type not in catalog["components"]:
            errors.append(f"{key}: type not found in catalog: {component_type}")
        if registry and component_type not in registry:
            errors.append(f"{key}: type not found in registry: {component_type}")

        children = element.get("children")
        if (
            catalog
            and isinstance(children, list)
            and children
            and component_type in catalog["components"]
            and component_type not in catalog["has_children"]
        ):
            warnings.append(f"{key}: type has children but catalog does not mark hasChildren: true: {component_type}")


def extract_catalog(path: Path, errors: list[str], warnings: list[str]) -> Optional[dict]:
    if not path.exists():
        errors.append(f"Catalog file does not exist: {path}")
        return None

    text = path.read_text(encoding="utf-8")
    components: set[str] = set()
    has_children: set[str] = set()
    current: Optional[str] = None
    in_components = False

    for line in text.splitlines():
        if re.match(r"\s{2}components\s*:\s*\{", line):
            in_components = True
            continue
        if in_components and re.match(r"\s{2}actions\s*:", line):
            break
        if not in_components:
            continue

        match = re.match(r"\s{4}([A-Z][A-Za-z0-9_]*)\s*:\s*\{", line)
        if match:
            current = match.group(1)
            components.add(current)
            continue
        if current and "hasChildren: true" in line:
            has_children.add(current)

    if not components:
        warnings.append(f"No catalog components detected in {path}")
    return {"components": components, "has_children": has_children}


def extract_registry(path: Path, errors: list[str], warnings: list[str]) -> Optional[set[str]]:
    if not path.exists():
        errors.append(f"Registry file does not exist: {path}")
        return None

    text = path.read_text(encoding="utf-8")
    registry = set(re.findall(r"^\s{2}([A-Z][A-Za-z0-9_]*)\s*:\s*\(", text, flags=re.MULTILINE))
    if not registry:
        warnings.append(f"No registry components detected in {path}")
    return registry


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
            print("UI tree validation failed:")
            for error in errors:
                print(f"- {error}")
        else:
            print("UI tree validation passed.")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
