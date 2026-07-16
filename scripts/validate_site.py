#!/usr/bin/env python3
"""Site-wide validation for a static GitHub Pages repository.

Uses only the Python standard library. It reports hard errors for broken local
links, missing fragments, duplicate HTML ids and invalid embedded JSON-LD.
Metadata and sitemap gaps are reported as warnings so they can be repaired in
small, reviewable batches.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


SITE_ORIGIN = "https://milos-timotijevic.github.io"
IGNORED_DIRS = {".git", ".github", "node_modules", "vendor"}
SKIPPED_SCHEMES = {"mailto", "tel", "javascript", "data"}


@dataclass(frozen=True)
class Finding:
    level: str
    path: Path
    message: str


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: list[str] = []
        self.canonical: str | None = None
        self.description: str | None = None
        self.html_lang: str | None = None
        self.title_parts: list[str] = []
        self.h1_count = 0
        self.jsonld_parts: list[list[str]] = []
        self._in_title = False
        self._in_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag == "html":
            self.html_lang = values.get("lang")
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self.h1_count += 1
        if tag in {"a", "area", "link"} and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"img", "script", "iframe", "source", "video", "audio"} and values.get("src"):
            self.links.append(values["src"] or "")
        if tag == "link" and "canonical" in (values.get("rel") or "").lower().split():
            self.canonical = values.get("href")
        if tag == "meta" and (values.get("name") or "").lower() == "description":
            self.description = values.get("content")
        if tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True
            self.jsonld_parts.append([])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_jsonld and self.jsonld_parts:
            self.jsonld_parts[-1].append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def iter_html(root: Path) -> list[Path]:
    pages: list[Path] = []
    for path in root.rglob("*.html"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        pages.append(path)
    return sorted(pages)


def expected_url(root: Path, page: Path) -> str:
    rel = page.relative_to(root).as_posix()
    if rel == "index.html":
        return SITE_ORIGIN + "/"
    if rel.endswith("/index.html"):
        return SITE_ORIGIN + "/" + rel[: -len("index.html")]
    return SITE_ORIGIN + "/" + rel


def resolve_local_target(root: Path, page: Path, href: str) -> tuple[Path, str] | None:
    href = href.strip()
    if not href or href.startswith("//"):
        return None
    parsed = urlsplit(href)
    if parsed.scheme.lower() in SKIPPED_SCHEMES:
        return None
    if parsed.scheme in {"http", "https"}:
        if parsed.netloc != "milos-timotijevic.github.io":
            return None
        raw_path = parsed.path
    elif parsed.scheme or parsed.netloc:
        return None
    else:
        raw_path = parsed.path
    if not raw_path and parsed.fragment:
        return page, unquote(parsed.fragment)
    if not raw_path:
        return None
    decoded = unquote(raw_path)
    if decoded.startswith("/"):
        target = root / decoded.lstrip("/")
    else:
        target = page.parent / decoded
    target = Path(os.path.normpath(target))
    try:
        target.relative_to(root)
    except ValueError:
        return target, unquote(parsed.fragment)
    if target.is_dir() or decoded.endswith("/"):
        target = target / "index.html"
    elif not target.suffix and (target / "index.html").exists():
        target = target / "index.html"
    return target, unquote(parsed.fragment)


def load_sitemap(root: Path) -> tuple[set[str], list[Finding]]:
    path = root / "sitemap.xml"
    if not path.exists():
        return set(), [Finding("warning", path, "sitemap.xml is missing")]
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return set(), [Finding("error", path, f"invalid sitemap XML: {exc}")]
    urls = {
        (node.text or "").strip()
        for node in tree.getroot().iter()
        if node.tag.endswith("loc") and (node.text or "").strip()
    }
    return urls, []


def validate(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    pages = iter_html(root)
    parsed_pages: dict[Path, PageParser] = {}
    sitemap_urls, sitemap_findings = load_sitemap(root)
    findings.extend(sitemap_findings)

    for page in pages:
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError) as exc:
            findings.append(Finding("error", page, f"cannot read HTML as UTF-8: {exc}"))
            continue
        parsed_pages[page] = parser
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        for duplicate in duplicates:
            findings.append(Finding("error", page, f"duplicate id: #{duplicate}"))
        for index, parts in enumerate(parser.jsonld_parts, start=1):
            payload = "".join(parts).strip()
            if not payload:
                findings.append(Finding("error", page, f"empty JSON-LD block {index}"))
                continue
            try:
                json.loads(payload)
            except json.JSONDecodeError as exc:
                findings.append(Finding("error", page, f"invalid JSON-LD block {index}: {exc.msg}"))

        if not parser.html_lang:
            findings.append(Finding("warning", page, "missing html lang attribute"))
        if not parser.title:
            findings.append(Finding("warning", page, "missing or empty title"))
        if not parser.description:
            findings.append(Finding("warning", page, "missing meta description"))
        if not parser.canonical:
            findings.append(Finding("warning", page, "missing canonical URL"))
        elif parser.canonical != expected_url(root, page):
            findings.append(Finding("warning", page, f"canonical differs from expected URL: {parser.canonical}"))
        if parser.h1_count != 1:
            findings.append(Finding("warning", page, f"expected one h1, found {parser.h1_count}"))
        url = expected_url(root, page)
        if sitemap_urls and url not in sitemap_urls:
            findings.append(Finding("warning", page, "page is missing from sitemap.xml"))

    for page, parser in parsed_pages.items():
        for href in parser.links:
            resolved = resolve_local_target(root, page, href)
            if resolved is None:
                continue
            target, fragment = resolved
            try:
                target.relative_to(root)
            except ValueError:
                findings.append(Finding("error", page, f"local link escapes repository root: {href}"))
                continue
            if not target.exists():
                findings.append(Finding("error", page, f"broken local target: {href}"))
                continue
            if fragment and target.suffix.lower() in {".html", ".htm"}:
                target_parser = parsed_pages.get(target)
                if target_parser is None:
                    try:
                        target_parser = PageParser()
                        target_parser.feed(target.read_text(encoding="utf-8"))
                    except (UnicodeDecodeError, OSError):
                        continue
                if fragment not in set(target_parser.ids):
                    findings.append(Finding("error", page, f"missing fragment #{fragment} in {target.relative_to(root)}"))
    return findings


def emit(root: Path, findings: list[Finding]) -> int:
    errors = sum(item.level == "error" for item in findings)
    warnings = sum(item.level == "warning" for item in findings)
    for item in findings:
        try:
            rel = item.path.relative_to(root).as_posix()
        except ValueError:
            rel = item.path.as_posix()
        print(f"::{item.level} file={rel}::{item.message}")
    print(f"Site-wide audit: {errors} error(s), {warnings} warning(s).")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the complete static site")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    return emit(root, validate(root))


if __name__ == "__main__":
    sys.exit(main())
