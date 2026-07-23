#!/usr/bin/env python3
"""Audit static-site delivery size and maintainability signals.

The audit intentionally uses only the Python standard library. It protects the
site from accidental page bloat while reporting useful inventory numbers for
future, reviewable optimisation work. It does not rewrite HTML or CSS.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


IGNORED_DIRS = {".git", ".github", "node_modules", "vendor"}
IGNORED_PAGES = {"articles/test.html", "google61a9ae6e657c98d9.html"}
MAX_HTML_BYTES = 256 * 1024
MAX_INLINE_STYLE_BYTES = 32 * 1024
MAX_TOTAL_INLINE_CSS_BYTES = 256 * 1024


def iter_html(root: Path) -> list[Path]:
    pages: list[Path] = []
    for path in root.rglob("*.html"):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if rel.as_posix() in IGNORED_PAGES:
            continue
        pages.append(path)
    return sorted(pages)


def normalise_css(css: str) -> str:
    return re.sub(r"\s+", " ", css).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit page size and inline-style maintainability"
    )
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    pages = iter_html(root)
    errors: list[str] = []
    page_sizes: list[tuple[int, str]] = []
    style_sizes: list[tuple[int, str]] = []
    style_fingerprints: Counter[str] = Counter()
    total_inline_css = 0

    for page in pages:
        rel = page.relative_to(root).as_posix()
        raw = page.read_bytes()
        page_sizes.append((len(raw), rel))
        if len(raw) > MAX_HTML_BYTES:
            errors.append(
                f"{rel}: HTML size {len(raw)} bytes exceeds "
                f"{MAX_HTML_BYTES}-byte budget"
            )

        text = raw.decode("utf-8", errors="replace")
        for block in re.findall(
            r"<style\b[^>]*>(.*?)</style>", text, flags=re.IGNORECASE | re.DOTALL
        ):
            size = len(block.encode("utf-8"))
            total_inline_css += size
            style_sizes.append((size, rel))
            style_fingerprints[normalise_css(block)] += 1
            if size > MAX_INLINE_STYLE_BYTES:
                errors.append(
                    f"{rel}: inline style block {size} bytes exceeds "
                    f"{MAX_INLINE_STYLE_BYTES}-byte budget"
                )

    if total_inline_css > MAX_TOTAL_INLINE_CSS_BYTES:
        errors.append(
            f"total inline CSS {total_inline_css} bytes exceeds "
            f"{MAX_TOTAL_INLINE_CSS_BYTES}-byte budget"
        )

    repeated_blocks = sum(count - 1 for count in style_fingerprints.values() if count > 1)
    largest_pages = sorted(page_sizes, reverse=True)[:5]
    largest_style = max(style_sizes, default=(0, "none"))

    print(f"Maintainability inventory: {len(pages)} HTML page(s)")
    print(f"Total HTML size: {sum(size for size, _ in page_sizes)} bytes")
    print(f"Total inline CSS size: {total_inline_css} bytes")
    print(f"Repeated inline style blocks: {repeated_blocks}")
    print(
        "Largest inline style block: "
        f"{largest_style[0]} bytes ({largest_style[1]})"
    )
    print("Largest HTML pages:")
    for size, rel in largest_pages:
        print(f"  - {rel}: {size} bytes")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Maintainability baseline: FAIL ({len(errors)} error(s))")
        return 1
    print("Maintainability baseline: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
