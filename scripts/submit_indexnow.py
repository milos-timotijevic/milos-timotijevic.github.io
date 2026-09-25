#!/usr/bin/env python3
"""Submit changed public HTML URLs to IndexNow.

Designed for milos-timotijevic.github.io. It can:
- map changed HTML repository files to public URLs,
- notify removals as well as additions/updates,
- bootstrap newly refreshed sitemap URLs when sitemap.xml changes,
- verify that the public IndexNow key is already reachable before submitting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

HOST = "milos-timotijevic.github.io"
ORIGIN = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/IndexNow"
KEY_FILE = "5f8f60c227a48ff8f435ee77f8aceacc.txt"
SITEMAP_FILE = "sitemap.xml"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def normalize_before(before: str, after: str) -> str:
    zeros = bool(before) and set(before) == {"0"}
    if not before or zeros:
        try:
            return run_git("rev-parse", f"{after}^").strip()
        except subprocess.CalledProcessError:
            return ""
    return before


def changed_paths(before: str, after: str) -> list[str]:
    before = normalize_before(before, after)
    if before:
        output = run_git("diff", "--name-only", before, after)
    else:
        output = run_git("ls-tree", "-r", "--name-only", after)
    return [line.strip() for line in output.splitlines() if line.strip()]


def path_to_url(path: str) -> str | None:
    if not path.endswith(".html"):
        return None
    if path == "index.html":
        return ORIGIN + "/"
    if path.endswith("/index.html"):
        return f"{ORIGIN}/{path[:-len('index.html')]}"
    return f"{ORIGIN}/{path}"


def sitemap_bootstrap_urls() -> set[str]:
    """Return public HTML/page URLs with the newest <lastmod> in the sitemap."""
    sitemap_path = Path(SITEMAP_FILE)
    if not sitemap_path.is_file():
        return set()

    root = ET.parse(sitemap_path).getroot()
    records: list[tuple[str, str]] = []

    for url_el in root.findall("sm:url", SITEMAP_NS):
        loc_el = url_el.find("sm:loc", SITEMAP_NS)
        lm_el = url_el.find("sm:lastmod", SITEMAP_NS)
        if loc_el is None or lm_el is None:
            continue
        loc = (loc_el.text or "").strip()
        lastmod = (lm_el.text or "").strip()
        if not loc or not lastmod:
            continue
        parsed = urlparse(loc)
        if parsed.scheme != "https" or parsed.netloc != HOST:
            continue
        # Submit human-facing pages, not JSON/CSV/XML data exports.
        if not (parsed.path.endswith(".html") or parsed.path.endswith("/")):
            continue
        records.append((lastmod, loc))

    if not records:
        return set()

    newest = max(lastmod for lastmod, _ in records)
    return {loc for lastmod, loc in records if lastmod == newest}


def wait_for_public_key(key: str, attempts: int = 18, delay: int = 10) -> bool:
    url = f"{ORIGIN}/{KEY_FILE}"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                content = response.read().decode("utf-8", errors="replace").strip()
            if content == key:
                print(f"IndexNow key verified at {url}.")
                return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass

        if attempt < attempts:
            print(f"Waiting for public IndexNow key (attempt {attempt}/{attempts})...")
            time.sleep(delay)

    print(f"ERROR: Public IndexNow key could not be verified at {url}.", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="")
    parser.add_argument("--after", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    key_path = Path(KEY_FILE)
    if not key_path.is_file():
        print(f"ERROR: IndexNow key file not found: {KEY_FILE}", file=sys.stderr)
        return 1

    key = key_path.read_text(encoding="utf-8").strip()
    if not (8 <= len(key) <= 128):
        print("ERROR: IndexNow key length is invalid.", file=sys.stderr)
        return 1
    if not all(ch.isalnum() or ch == "-" for ch in key):
        print("ERROR: IndexNow key contains invalid characters.", file=sys.stderr)
        return 1

    paths = changed_paths(args.before, args.after)
    urls = {
        url
        for path in paths
        if (url := path_to_url(path)) is not None
    }

    # When sitemap.xml itself is refreshed, bootstrap the human-facing URLs whose
    # lastmod is the newest date in the sitemap. This covers the first deployment
    # of IndexNow after a batch harmonization.
    if SITEMAP_FILE in paths:
        urls.update(sitemap_bootstrap_urls())

    urls = sorted(urls)

    if not urls:
        print("No changed public HTML URLs to submit to IndexNow.")
        return 0

    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{ORIGIN}/{KEY_FILE}",
        "urlList": urls,
    }

    print(f"IndexNow URLs: {len(urls)}")
    for url in urls:
        print(f"- {url}")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not wait_for_public_key(key):
        return 1

    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        print(f"ERROR: IndexNow request failed: {exc}", file=sys.stderr)
        return 1

    print(f"IndexNow HTTP status: {status}")
    if body:
        print(body)

    if status in (200, 202):
        return 0

    print("ERROR: IndexNow submission was not accepted.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
