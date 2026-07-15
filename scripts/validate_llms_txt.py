#!/usr/bin/env python3
"""Validate the site's root llms.txt discovery file."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LLMS_PATH = ROOT / "llms.txt"
REQUIRED_SECTIONS = {
    "Core pages",
    "Machine-readable data",
    "Research framework and clusters",
    "Publication collections",
    "Optional",
}
REQUIRED_URLS = {
    "https://milos-timotijevic.github.io/",
    "https://milos-timotijevic.github.io/bibliography/",
    "https://milos-timotijevic.github.io/knowledge-graph/",
    "https://milos-timotijevic.github.io/data/",
    "https://milos-timotijevic.github.io/data/publications.jsonld",
    "https://milos-timotijevic.github.io/data/knowledge-graph.jsonld",
    "https://milos-timotijevic.github.io/data/manifest.json",
}


def main() -> int:
    errors: list[str] = []
    if not LLMS_PATH.is_file():
        print(f"FAIL: missing {LLMS_PATH}", file=sys.stderr)
        return 1

    text = LLMS_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        errors.append("The first line must be a single H1 title.")
    if not any(line.startswith("> ") for line in lines[:8]):
        errors.append("A blockquote summary is required near the top.")

    sections = {line[3:].strip() for line in lines if line.startswith("## ")}
    missing_sections = sorted(REQUIRED_SECTIONS - sections)
    if missing_sections:
        errors.append(f"Missing sections: {missing_sections}")

    links = re.findall(r"^- \[[^\]]+\]\((https://[^)]+)\): .+$", text, re.MULTILINE)
    if len(links) < 20:
        errors.append(f"Expected at least 20 described links; found {len(links)}.")
    duplicates = sorted({url for url in links if links.count(url) > 1})
    if duplicates:
        errors.append(f"Duplicate URLs: {duplicates}")
    missing_urls = sorted(REQUIRED_URLS - set(links))
    if missing_urls:
        errors.append(f"Missing required URLs: {missing_urls}")

    for url in links:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"Invalid absolute HTTPS URL: {url}")

    if errors:
        print("FAIL: llms.txt validation found problems", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("PASS: llms.txt validation completed successfully")
    print(f"  sections: {len(sections)}")
    print(f"  described links: {len(links)}")
    print(f"  unique URLs: {len(set(links))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

