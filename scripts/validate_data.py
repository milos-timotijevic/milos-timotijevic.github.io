#!/usr/bin/env python3
"""Validate publications.csv and its publications.json export."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


EXPECTED_FIELDS = [
    "id",
    "type",
    "year",
    "author_sr",
    "author_en",
    "title_sr",
    "title_en",
    "doi_work_or_edition",
    "doi_landing_page",
    "doi_repository",
    "doi_note",
    "landing_page",
    "zenodo",
    "wikidata",
    "cobiss",
    "cluster",
    "status",
]

ALLOWED_STATUSES = {
    "checked",
    "draft",
    "needs_update",
    "needs_review",
    "waiting_indexing",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate data/publications.csv and data/publications.json."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: inferred from this script).",
    )
    return parser.parse_args()


def main() -> int:
    root = parse_args().root.resolve()
    csv_path = root / "data" / "publications.csv"
    json_path = root / "data" / "publications.json"
    errors: list[str] = []

    if not csv_path.is_file():
        errors.append(f"Missing file: {csv_path}")
    if not json_path.is_file():
        errors.append(f"Missing file: {json_path}")
    if errors:
        return report(errors)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_fields = reader.fieldnames or []
        if actual_fields != EXPECTED_FIELDS:
            errors.append(
                "CSV columns differ from the expected schema:\n"
                f"  expected: {EXPECTED_FIELDS}\n"
                f"  actual:   {actual_fields}"
            )
        rows = list(reader)

    for number, row in enumerate(rows, start=2):
        if None in row:
            errors.append(f"CSV row {number} contains extra unnamed columns.")

    identifiers = [row.get("id", "").strip() for row in rows]
    empty_ids = [index + 2 for index, value in enumerate(identifiers) if not value]
    if empty_ids:
        errors.append(f"Empty id values in CSV rows: {empty_ids}")
    duplicate_ids = sorted(
        value for value, count in Counter(identifiers).items() if value and count > 1
    )
    if duplicate_ids:
        errors.append(f"Duplicate id values: {duplicate_ids}")

    qids = [row.get("wikidata", "").strip() for row in rows if row.get("wikidata", "").strip()]
    duplicate_qids = sorted(value for value, count in Counter(qids).items() if count > 1)
    if duplicate_qids:
        errors.append(f"Duplicate non-empty Wikidata identifiers: {duplicate_qids}")

    invalid_statuses = sorted(
        {
            row.get("status", "").strip()
            for row in rows
            if row.get("status", "").strip() not in ALLOWED_STATUSES
        }
    )
    if invalid_statuses:
        errors.append(f"Unsupported status values: {invalid_statuses}")

    try:
        with json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read valid JSON from {json_path}: {exc}")
        return report(errors)

    expected_records = [
        {field: (row.get(field, "").strip() or None) for field in EXPECTED_FIELDS}
        for row in rows
    ]
    if payload.get("recordCount") != len(rows):
        errors.append(
            f"JSON recordCount is {payload.get('recordCount')!r}; expected {len(rows)}."
        )
    if payload.get("fields") != EXPECTED_FIELDS:
        errors.append("JSON fields do not match the CSV schema.")
    if payload.get("records") != expected_records:
        errors.append("JSON records do not exactly match normalized CSV records.")

    status_counts = Counter(row.get("status", "").strip() for row in rows)
    if errors:
        return report(errors)

    print("PASS: open-data validation completed successfully")
    print(f"  records: {len(rows)}")
    print(f"  unique ids: {len(set(identifiers))}")
    print(f"  non-empty Wikidata ids: {len(qids)}")
    print(f"  statuses: {dict(sorted(status_counts.items()))}")
    print("  publications.json exactly matches publications.csv")
    return 0


def report(errors: list[str]) -> int:
    print("FAIL: open-data validation found problems", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
