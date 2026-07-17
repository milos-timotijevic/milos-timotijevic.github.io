#!/usr/bin/env python3
"""Regression checks for the redesigned bilingual homepage."""

from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path


REQUIRED_IDS = {
    "top",
    "entry-points",
    "biografija",
    "biography",
    "profiles",
    "authority-identifiers",
    "official-profile",
    "awards",
    "selected-works",
    "bibliografija",
    "public-activity",
    "digital-infrastructure",
    "kontakt",
    "site-search",
}

NAV_LABELS = {
    "Профил / Profile",
    "Публикације / Publications",
    "Јавни рад / Public Activity",
    "Дигитална инфраструктура / Digital Infrastructure",
}

ROUTE_CARDS = {
    "Библиографија / Bibliography",
    "Теме / Research Themes",
    "Подаци / Data",
    "Музејски рад / Museum Work",
    "Стручни рад / Professional Service",
}

TOPIC_LINKS = {
    "/knowledge-graph/": "модерна српска историја / Modern Serbian History",
    "/knowledge-graph/research/local-modernity-symbolic-power.html": "локална модерност / Local Modernity",
    "/knowledge-graph/research/political-rituals-symbolic-politics.html": "политичка култура / Political Culture",
    "/knowledge-graph/research/culture-nationalism-symbolic-representation.html": "симболичке праксе / Symbolic Practices",
    "/knowledge-graph/research/war-propaganda-memory.html": "култура сећања / Memory Culture",
    "/knowledge-graph/research/cultural-heritage-museums-public-history.html": "јавна историја / Public History",
    "/knowledge-graph/research/cacak-local-modernity-case-study.html": "Чачак и западна Србија / Čačak and Western Serbia",
}


def visible_text(fragment: str) -> str:
    fragment = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<style\b.*?</style>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(unescape(fragment).split())


def section_between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        return ""
    end = source.find(end_marker, start + len(start_marker))
    return source[start:] if end < 0 else source[start:end]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "index.html"
    if not path.exists():
        return ["index.html is missing"]

    source = path.read_text(encoding="utf-8")
    text = visible_text(source)

    if not re.search(r"<meta\s+charset=[\"']?utf-8", source, re.I):
        errors.append("missing UTF-8 charset declaration")
    if not re.search(r"<meta[^>]+name=[\"']viewport[\"'][^>]+content=[\"'][^\"']*width=device-width", source, re.I):
        errors.append("missing mobile viewport metadata")
    if not re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'][^\"']+", source, re.I):
        errors.append("missing non-empty meta description")
    if not re.search(r"<link[^>]+rel=[\"']canonical[\"'][^>]+href=[\"']https://milos-timotijevic\.github\.io/[\"']", source, re.I):
        errors.append("homepage canonical URL is missing or incorrect")
    if len(re.findall(r"<h1\b", source, re.I)) != 1:
        errors.append("homepage must contain exactly one h1")

    ids = re.findall(r"\bid=[\"']([^\"']+)[\"']", source, re.I)
    missing_ids = sorted(REQUIRED_IDS - set(ids))
    if missing_ids:
        errors.append("missing required ids: " + ", ".join(missing_ids))
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        errors.append("duplicate ids: " + ", ".join(duplicates))

    for label in sorted(NAV_LABELS):
        if label not in text:
            errors.append(f"missing bilingual navigation label: {label}")

    entry = section_between(source, '<section id="entry-points"', '<section id="biografija"')
    if not entry:
        errors.append("cannot locate entry-points section")
    else:
        headings = {
            visible_text(value)
            for value in re.findall(r"<h3\b[^>]*>(.*?)</h3>", entry, re.I | re.S)
        }
        missing_cards = sorted(ROUTE_CARDS - headings)
        if missing_cards:
            errors.append("missing route cards: " + ", ".join(missing_cards))
        if len(re.findall(r"class=[\"'][^\"']*\bentry-point-card\b", entry, re.I)) != 5:
            errors.append("entry-points section must contain exactly five route cards")

    topics = section_between(source, '<p class="topic-line">', '<div class="intro">')
    if not topics:
        errors.append("cannot locate main topics block")
    else:
        if "Главне теме / Main Topics:" not in visible_text(topics):
            errors.append("main topics heading is not bilingual")
        for href, label in TOPIC_LINKS.items():
            pattern = rf'<a\s+[^>]*href=[\"\']{re.escape(href)}[\"\'][^>]*>(.*?)</a>'
            match = re.search(pattern, topics, re.I | re.S)
            if not match:
                errors.append(f"missing topic link: {href}")
            elif visible_text(match.group(1)) != label:
                errors.append(f"topic label differs for {href}: {visible_text(match.group(1))!r}")

    footer_match = re.search(r"<footer\b[^>]*>(.*?)</footer>", source, re.I | re.S)
    footer = visible_text(footer_match.group(1)) if footer_match else ""
    if "Последње ажурирање / Last updated:" not in footer:
        errors.append("visible bilingual last-updated text is missing from footer")
    if footer_match and re.search(r"<a\b[^>]*>[^<]*(?:Последње ажурирање|Last updated)", footer_match.group(1), re.I):
        errors.append("last-updated value must be visible text, not a link")

    if not re.search(r"@media\s*\(max-width\s*:\s*\d+px\)", source, re.I):
        errors.append("missing responsive mobile CSS media query")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Homepage contract: FAIL ({len(errors)} error(s))")
        return 1
    print("Homepage contract: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
