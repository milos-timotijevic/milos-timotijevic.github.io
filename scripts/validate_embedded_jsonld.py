#!/usr/bin/env python3
"""Validate JSON-LD embedded in the site's principal public HTML pages."""

from html.parser import HTMLParser
import json
from pathlib import Path
import sys


REQUIRED_PAGES = (
    "index.html",
    "bibliography/index.html",
    "knowledge-graph/index.html",
    "data/index.html",
    "citation/index.html",
)


class JsonLdExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._capturing = False
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attributes = {name.lower(): value for name, value in attrs}
        script_type = (attributes.get("type") or "").lower().strip()
        if script_type == "application/ld+json":
            self._capturing = True
            self._parts = []

    def handle_data(self, data):
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._capturing:
            self.blocks.append("".join(self._parts).strip())
            self._capturing = False
            self._parts = []


def has_context(value):
    if isinstance(value, dict):
        if "@context" in value:
            return True
        return any(has_context(child) for child in value.values())
    if isinstance(value, list):
        return any(has_context(child) for child in value)
    return False


def has_entity_shape(value):
    if isinstance(value, dict):
        if "@type" in value or "@graph" in value:
            return True
        return any(has_entity_shape(child) for child in value.values())
    if isinstance(value, list):
        return any(has_entity_shape(child) for child in value)
    return False


def main() -> int:
    repository_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    errors = []
    total_blocks = 0

    for relative_path in REQUIRED_PAGES:
        page_path = repository_root / relative_path
        if not page_path.is_file():
            errors.append(f"Required public page is missing: {relative_path}")
            continue

        try:
            html = page_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{relative_path}: cannot read UTF-8 HTML: {exc}")
            continue

        parser = JsonLdExtractor()
        parser.feed(html)
        parser.close()

        if not parser.blocks:
            errors.append(f"{relative_path}: no application/ld+json block found.")
            continue

        for position, block in enumerate(parser.blocks, start=1):
            total_blocks += 1
            if not block:
                errors.append(f"{relative_path}, block {position}: JSON-LD is empty.")
                continue
            try:
                value = json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"{relative_path}, block {position}: invalid JSON: "
                    f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
                )
                continue
            if not isinstance(value, (dict, list)):
                errors.append(
                    f"{relative_path}, block {position}: top level must be object or array."
                )
            if not has_context(value):
                errors.append(
                    f"{relative_path}, block {position}: JSON-LD lacks @context."
                )
            if not has_entity_shape(value):
                errors.append(
                    f"{relative_path}, block {position}: lacks @type or @graph."
                )

    if errors:
        print("Embedded JSON-LD validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"Embedded JSON-LD validation passed: {total_blocks} blocks across "
        f"{len(REQUIRED_PAGES)} principal public pages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
