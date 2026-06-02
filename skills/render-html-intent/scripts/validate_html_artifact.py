#!/usr/bin/env python3
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = set()
        self.title_text = []
        self.in_title = False
        self.meta_viewport = False
        self.body_text = []
        self.in_body = False
        self.styles = 0
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "body":
            self.in_body = True
        if tag == "meta" and attrs_dict.get("name", "").lower() == "viewport":
            self.meta_viewport = True
        if tag == "style":
            self.styles += 1
        if tag == "script":
            self.scripts += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_title:
            self.title_text.append(data)
        if self.in_body:
            self.body_text.append(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a standalone rendered HTML artifact.")
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    errors = []
    warnings = []

    if not args.html_file.exists():
        errors.append(f"File does not exist: {args.html_file}")
        return emit(args.json, errors, warnings)

    text = args.html_file.read_text(encoding="utf-8")
    lower = text.lower()
    parsed = StructureParser()
    parsed.feed(text)

    if "<!doctype html" not in lower[:200]:
        errors.append("Missing <!doctype html> near the top of the file.")
    for tag in ("html", "head", "body"):
        if tag not in parsed.tags:
            errors.append(f"Missing <{tag}> tag.")
    if not "".join(parsed.title_text).strip():
        errors.append("Missing non-empty <title>.")
    if not parsed.meta_viewport:
        errors.append("Missing viewport meta tag.")
    if len(" ".join(parsed.body_text).split()) < 8:
        errors.append("Body text appears empty or too sparse to inspect.")
    if parsed.styles == 0:
        warnings.append("No <style> block found; standalone artifacts usually need one.")

    placeholder_patterns = [
        r"\{\{[A-Z0-9_-]+\}\}",
        r"\bTODO\b",
        r"\bLorem ipsum\b",
        r"placeholder",
    ]
    for pattern in placeholder_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"Unresolved placeholder-like text matched: {pattern}")

    broken_asset = re.findall(r"""(?:src|href)=["'](?:#|/path/to/|image\.|asset\.)""", text)
    if broken_asset:
        errors.append("Found likely broken asset references.")

    return emit(args.json, errors, warnings)


def emit(as_json: bool, errors: list[str], warnings: list[str]) -> int:
    if as_json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, indent=2))
    else:
        if errors:
            print("HTML artifact validation failed:")
            for error in errors:
                print(f"- {error}")
        else:
            print("HTML artifact validation passed.")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
