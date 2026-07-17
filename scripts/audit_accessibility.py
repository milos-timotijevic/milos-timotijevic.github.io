#!/usr/bin/env python3
"""Audit objective accessibility and mobile-usage signals in site HTML.

Phase 7D starts by enforcing the homepage contract while inventorying the
remaining pages. Later repair batches can progressively make the inventory
checks strict without hiding the current state.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CONTENT_EXCLUSIONS = {
    "google61a9ae6e657c98d9.html",
    "articles/test.html",
}


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    pages = sorted(root.rglob("*.html"))
    errors: list[str] = []
    warnings: list[str] = []

    for page in pages:
        rel = page.relative_to(root).as_posix()
        if rel in CONTENT_EXCLUSIONS:
            continue
        text = page.read_text(encoding="utf-8", errors="replace")

        if not has(r"<meta\s+[^>]*name=[\"']viewport[\"']", text):
            warnings.append(f"missing viewport: {rel}")
        if not has(r"<main(?:\s|>)", text):
            warnings.append(f"missing main landmark: {rel}")
        if not has(r"<a\s+[^>]*href=[\"']#[^\"']+[\"'][^>]*>.*?(skip|прескочи)", text):
            warnings.append(f"missing skip link: {rel}")

        for match in re.finditer(r"<img\b[^>]*>", text, flags=re.IGNORECASE):
            if not has(r"\balt\s*=", match.group(0)):
                errors.append(f"image without alt attribute: {rel}")

    homepage = (root / "index.html").read_text(encoding="utf-8")
    homepage_requirements = {
        "homepage main landmark": r"<main\s+[^>]*id=[\"']main-content[\"']",
        "homepage skip link": r"<a\s+[^>]*class=[\"'][^\"']*skip-link[^\"']*[\"'][^>]*href=[\"']#main-content[\"']",
        "homepage viewport": r"<meta\s+[^>]*name=[\"']viewport[\"']",
    }
    for label, pattern in homepage_requirements.items():
        if not has(pattern, homepage):
            errors.append(f"missing {label}")

    print(f"Accessibility inventory: {len(pages)} HTML page(s)")
    print(f"Inventory warnings: {len(warnings)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Accessibility baseline: FAIL ({len(errors)} error(s))")
        return 1
    print("Accessibility baseline: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
