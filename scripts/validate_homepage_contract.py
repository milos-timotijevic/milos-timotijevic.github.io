#!/usr/bin/env python3
"""Regression checks for the bilingual homepage.

The checks are intentionally insensitive to HTML attribute order so that
semantically equivalent serialization (for example by BeautifulSoup) does not
cause false failures.
"""

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
    "Ентитети / Entity Graph",
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


def tag_has_attr(source: str, tag: str, attr: str, value_pattern: str) -> bool:
    """Match an HTML tag attribute regardless of attribute order."""
    pattern = (
        rf"<{tag}\b"
        rf"(?=[^>]*\b{re.escape(attr)}=[\"']{value_pattern}[\"'])"
        rf"[^>]*>"
    )
    return re.search(pattern, source, re.I | re.S) is not None


def tag_has_attrs(source: str, tag: str, attrs: list[tuple[str, str]]) -> bool:
    lookaheads = "".join(
        rf"(?=[^>]*\b{re.escape(name)}=[\"']{value}[\"'])"
        for name, value in attrs
    )
    return re.search(rf"<{tag}\b{lookaheads}[^>]*>", source, re.I | re.S) is not None


def section_by_id(source: str, section_id: str) -> str:
    """Return one <section id=...> block regardless of attribute order."""
    start_match = re.search(
        rf"<section\b(?=[^>]*\bid=[\"']{re.escape(section_id)}[\"'])[^>]*>",
        source,
        re.I | re.S,
    )
    if not start_match:
        return ""

    # Homepage sections are not nested inside each other, so the next section
    # start safely marks the end of the current one for these regression checks.
    next_match = re.search(r"<section\b", source[start_match.end():], re.I)
    if not next_match:
        return source[start_match.start():]

    end = start_match.end() + next_match.start()
    return source[start_match.start():end]


def block_by_class(source: str, tag: str, class_name: str) -> str:
    start_match = re.search(
        rf"<{tag}\b(?=[^>]*\bclass=[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"'])[^>]*>",
        source,
        re.I | re.S,
    )
    if not start_match:
        return ""

    close = re.search(rf"</{tag}>", source[start_match.end():], re.I)
    if not close:
        return source[start_match.start():]
    end = start_match.end() + close.end()
    return source[start_match.start():end]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "index.html"
    if not path.exists():
        return ["index.html is missing"]

    source = path.read_text(encoding="utf-8")
    text = visible_text(source)

    if not re.search(r"<meta\s+charset=[\"']?utf-8", source, re.I):
        errors.append("missing UTF-8 charset declaration")

    if not tag_has_attrs(
        source,
        "meta",
        [
            ("name", r"viewport"),
            ("content", r"[^\"']*width=device-width[^\"']*"),
        ],
    ):
        errors.append("missing mobile viewport metadata")

    if not tag_has_attrs(
        source,
        "meta",
        [
            ("name", r"description"),
            ("content", r"[^\"']+"),
        ],
    ):
        errors.append("missing non-empty meta description")

    if not tag_has_attrs(
        source,
        "link",
        [
            ("rel", r"canonical"),
            ("href", r"https://milos-timotijevic\.github\.io/"),
        ],
    ):
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

    entry = section_by_id(source, "entry-points")
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

        card_count = len(
            re.findall(
                r"class=[\"'][^\"']*\bentry-point-card\b[^\"']*[\"']",
                entry,
                re.I,
            )
        )
        if card_count != 6:
            errors.append(
                f"entry-points section must contain exactly six route cards (found {card_count})"
            )

    topics = block_by_class(source, "p", "topic-line")
    if not topics:
        errors.append("cannot locate main topics block")
    else:
        if "Главне теме / Main Topics:" not in visible_text(topics):
            errors.append("main topics heading is not bilingual")

        for href, label in TOPIC_LINKS.items():
            pattern = rf'<a\s+[^>]*href=["\']{re.escape(href)}["\'][^>]*>(.*?)</a>'
            match = re.search(pattern, topics, re.I | re.S)
            if not match:
                errors.append(f"missing topic link: {href}")
            elif visible_text(match.group(1)) != label:
                errors.append(
                    f"topic label differs for {href}: {visible_text(match.group(1))!r}"
                )

    footer_match = re.search(r"<footer\b[^>]*>(.*?)</footer>", source, re.I | re.S)
    footer = visible_text(footer_match.group(1)) if footer_match else ""
    if "Последње ажурирање / Last updated:" not in footer:
        errors.append("visible bilingual last-updated text is missing from footer")

    if footer_match and re.search(
        r"<a\b[^>]*>[^<]*(?:Последње ажурирање|Last updated)",
        footer_match.group(1),
        re.I,
    ):
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
