#!/usr/bin/env python3
"""Validate CSV, JSON and JSON-LD bibliography exports."""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    jsonld_path = root / "data" / "publications.jsonld"
    manifest_path = root / "data" / "manifest.json"
    errors: list[str] = []

    if not csv_path.is_file():
        errors.append(f"Missing file: {csv_path}")
    if not json_path.is_file():
        errors.append(f"Missing file: {json_path}")
    if not jsonld_path.is_file():
        errors.append(f"Missing file: {jsonld_path}")
    if not manifest_path.is_file():
        errors.append(f"Missing file: {manifest_path}")
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

    try:
        with jsonld_path.open("r", encoding="utf-8") as handle:
            jsonld_payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read valid JSON-LD from {jsonld_path}: {exc}")
        return report(errors)

    graph = jsonld_payload.get("@graph")
    if not isinstance(graph, list) or not graph:
        errors.append("JSON-LD @graph is missing or empty.")
        work_nodes = []
    else:
        work_nodes = graph[1:]
        dataset = graph[0]
        if dataset.get("@type") != "Dataset":
            errors.append("First JSON-LD node must be the Dataset node.")
        if len(dataset.get("hasPart", [])) != len(rows):
            errors.append("JSON-LD Dataset hasPart count differs from CSV row count.")
    if len(work_nodes) != len(rows):
        errors.append(
            f"JSON-LD contains {len(work_nodes)} work nodes; expected {len(rows)}."
        )
    node_ids = [node.get("@id") for node in work_nodes]
    if any(not node_id for node_id in node_ids):
        errors.append("One or more JSON-LD work nodes have no @id.")
    if len(set(node_ids)) != len(node_ids):
        errors.append("JSON-LD work-node @id values are not unique.")
    csv_ids = set(identifiers)
    jsonld_ids = {
        value
        for node in work_nodes
        for value in (
            node.get("identifier", [])
            if isinstance(node.get("identifier"), list)
            else [node.get("identifier")]
        )
        if isinstance(value, str)
    }
    if jsonld_ids != csv_ids:
        errors.append("JSON-LD stable identifiers do not exactly match CSV ids.")

    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read valid JSON from {manifest_path}: {exc}")
        return report(errors)

    if manifest.get("schemaVersion") != 1:
        errors.append("Manifest schemaVersion must be 1.")
    if manifest.get("algorithm") != "SHA-256":
        errors.append("Manifest algorithm must be SHA-256.")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        errors.append("Manifest files must be a list.")
        entries = []
    expected_paths = {
        "data/publications.csv": (csv_path, len(rows)),
        "data/publications.json": (json_path, len(rows)),
        "data/publications.jsonld": (jsonld_path, len(rows)),
        "data/wikidata-items.csv": (root / "data" / "wikidata-items.csv", 111),
        "data/doi-list.csv": (root / "data" / "doi-list.csv", 67),
        "data/knowledge-graph.jsonld": (root / "data" / "knowledge-graph.jsonld", 12),
    }
    entries_by_path = {
        entry.get("path"): entry for entry in entries if isinstance(entry, dict)
    }
    if set(entries_by_path) != set(expected_paths):
        errors.append("Manifest file list differs from the expected machine-readable exports.")
    for relative_path, (path, expected_count) in expected_paths.items():
        entry = entries_by_path.get(relative_path)
        if not entry:
            continue
        content = path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if entry.get("sha256") != actual_hash:
            errors.append(f"Manifest SHA-256 mismatch for {relative_path}.")
        if entry.get("byteSize") != len(content):
            errors.append(f"Manifest byteSize mismatch for {relative_path}.")
        if entry.get("recordCount") != expected_count:
            errors.append(f"Manifest recordCount mismatch for {relative_path}.")

    status_counts = Counter(row.get("status", "").strip() for row in rows)
    if errors:
        return report(errors)

    print("PASS: open-data validation completed successfully")
    print(f"  records: {len(rows)}")
    print(f"  unique ids: {len(set(identifiers))}")
    print(f"  non-empty Wikidata ids: {len(qids)}")
    print(f"  statuses: {dict(sorted(status_counts.items()))}")
    print("  publications.json exactly matches publications.csv")
    print(f"  publications.jsonld contains {len(work_nodes)} Schema.org work nodes")
    print("  manifest SHA-256 values, byte sizes and record counts match all exports")
    return 0


def report(errors: list[str]) -> int:
    print("FAIL: open-data validation found problems", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

