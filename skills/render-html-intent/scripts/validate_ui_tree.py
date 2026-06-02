#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a simple flat UI tree JSON file.")
    parser.add_argument("tree_file", type=Path)
    args = parser.parse_args()

    try:
        tree = json.loads(args.tree_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Failed to read file: {args.tree_file}")
        return 1
    except OSError as error:
        print(f"Failed to read file {args.tree_file}: {error}")
        return 1
    except json.JSONDecodeError as error:
        print(f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}")
        return 1

    errors: list[str] = []

    if not isinstance(tree, dict):
        errors.append("Tree must be an object.")
        return emit(errors)

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

    return emit(errors)


def emit(errors: list[str]) -> int:
    if errors:
        print("UI tree validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("UI tree validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
