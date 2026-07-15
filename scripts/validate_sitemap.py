#!/usr/bin/env python3
"""Validate the public sitemap without third-party dependencies."""

from collections import Counter
from datetime import date
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


SITE_HOST = "milos-timotijevic.github.io"
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
REQUIRED_URLS = {
    f"https://{SITE_HOST}/",
    f"https://{SITE_HOST}/bibliography/",
    f"https://{SITE_HOST}/citation/",
    f"https://{SITE_HOST}/data/",
    f"https://{SITE_HOST}/knowledge-graph/",
}


def main() -> int:
    sitemap_path = Path(sys.argv[1] if len(sys.argv) > 1 else "sitemap.xml")
    errors: list[str] = []

    if not sitemap_path.is_file():
        print(f"ERROR: Sitemap file not found: {sitemap_path}")
        return 1

    try:
        root = ET.parse(sitemap_path).getroot()
    except ET.ParseError as exc:
        print(f"ERROR: Invalid XML: {exc}")
        return 1

    expected_root = f"{{{SITEMAP_NAMESPACE}}}urlset"
    if root.tag != expected_root:
        errors.append(
            f"Expected root element {expected_root!r}, found {root.tag!r}."
        )

    locations: list[str] = []
    for position, url_element in enumerate(
        root.findall(f"{{{SITEMAP_NAMESPACE}}}url"), start=1
    ):
        location_element = url_element.find(f"{{{SITEMAP_NAMESPACE}}}loc")
        if location_element is None or not (location_element.text or "").strip():
            errors.append(f"URL entry {position} has no non-empty <loc> value.")
            continue

        location = (location_element.text or "").strip()
        locations.append(location)
        parsed = urlparse(location)

        if parsed.scheme != "https":
            errors.append(f"{location}: URL must use HTTPS.")
        if parsed.netloc != SITE_HOST:
            errors.append(f"{location}: URL must use host {SITE_HOST}.")
        if parsed.query or parsed.fragment:
            errors.append(f"{location}: sitemap URL must not contain query or fragment.")

        last_modified = url_element.find(f"{{{SITEMAP_NAMESPACE}}}lastmod")
        if last_modified is not None and (last_modified.text or "").strip():
            value = (last_modified.text or "").strip()
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{location}: invalid ISO date in <lastmod>: {value!r}.")

    if not locations:
        errors.append("The sitemap contains no URL entries.")

    for location, count in Counter(locations).items():
        if count > 1:
            errors.append(f"Duplicate URL ({count} occurrences): {location}")

    missing_required = sorted(REQUIRED_URLS.difference(locations))
    for location in missing_required:
        errors.append(f"Required discovery URL is missing: {location}")

    if errors:
        print("Sitemap validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"Sitemap validation passed: {len(locations)} unique HTTPS URLs "
        f"on {SITE_HOST}; all required discovery pages are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
