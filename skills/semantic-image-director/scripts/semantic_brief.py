#!/usr/bin/env python3
"""Create a first-pass semantic image brief from a request."""

from __future__ import annotations

import argparse
import re
import sys


RISKY_TERMS = {
    "cloud": ("technical", "cloud computing or distributed infrastructure", "weather clouds, sky, meteorology"),
    "agent": ("technical", "AI/software actor or delegated worker", "spy, secret agent, human agent unless requested"),
    "model": ("technical", "computational/conceptual model", "fashion model, toy model"),
    "state": ("technical", "system condition over time", "geographic/political state unless requested"),
    "pipeline": ("technical", "ordered processing flow", "oil/gas/plumbing pipe unless requested"),
    "memory": ("technical", "stored context or information state", "human brain imagery unless requested"),
    "container": ("technical", "software/runtime package boundary", "shipping container unless requested"),
    "runtime": ("technical", "execution environment", "clock/race imagery"),
    "token": ("technical", "unit of text/value/access", "coin/game token unless requested"),
    "branch": ("technical/metaphorical", "version-control or decision branch", "tree branch unless requested"),
    "tree": ("technical/metaphorical", "hierarchy or decision structure", "literal tree unless requested"),
    "architecture": ("technical", "system/product structure", "buildings unless requested"),
    "stack": ("technical", "technology layers", "pile of objects unless requested"),
    "skill": ("technical", "reusable agent practice", "sports/school/magic ability"),
    "object": ("technical", "encapsulated behavior/state", "random physical object"),
    "function": ("technical", "operation or mapping", "event/function party"),
    "tool": ("technical", "capability interface", "hammer/wrench unless requested"),
    "pattern": ("technical", "reusable structure", "decorative pattern unless requested"),
    "episode": ("domain", "bounded clinical/product journey", "TV episode unless requested"),
    "journey": ("metaphorical", "process over time", "travel scene unless requested"),
    "lightcone": ("metaphorical/technical", "causal reach over time", "sci-fi cone unless requested"),
    "flush": ("technical/metaphorical", "release/drain/commit effect", "toilet unless requested"),
}


def find_terms(text: str) -> list[tuple[str, tuple[str, str, str]]]:
    found: list[tuple[str, tuple[str, str, str]]] = []
    lowered = text.lower()
    for term, data in RISKY_TERMS.items():
        if re.search(rf"\b{re.escape(term)}s?\b", lowered):
            found.append((term, data))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="*", help="Visual request. If omitted, stdin is used.")
    parser.add_argument("--route", choices=["auto", "imagegen", "deterministic", "hybrid"], default="auto")
    args = parser.parse_args()

    text = " ".join(args.request).strip() or sys.stdin.read().strip()
    if not text:
        print("Provide a visual request as arguments or stdin.", file=sys.stderr)
        return 2

    terms = find_terms(text)

    print("# Semantic Visual Brief")
    print()
    print("## Intent")
    print()
    print(text)
    print()
    print("## Renderer Route")
    print()
    print(args.route)
    print()
    print("## Semantic Lock")
    print()
    if terms:
        for term, (kind, meaning, forbidden) in terms:
            print(f"- `{term}`: class `{kind}`; intended meaning: {meaning}; do not depict: {forbidden}.")
    else:
        print("- No high-risk terms from the built-in list were detected. Still inspect domain language manually.")
    print()
    print("## Negative Semantics")
    print()
    print("Do not literalize technical, metaphorical, or domain terms as stock objects unless explicitly requested.")
    print()
    print("## Prompt Skeleton")
    print()
    print("```text")
    print("Primary artifact: <what should be created>")
    print("Domain meaning: <what the artifact is really about>")
    print("Must show: <visible elements>")
    print("Must preserve: <exact text/layout/structure>")
    print("Ambiguous terms:")
    for term, (_kind, meaning, forbidden) in terms:
        print(f'- "{term}" means {meaning}. Do not depict {forbidden}.')
    print("Negative semantics: Do not literalize technical terms as unrelated stock imagery.")
    print("Renderer route: <imagegen | deterministic | hybrid>")
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
