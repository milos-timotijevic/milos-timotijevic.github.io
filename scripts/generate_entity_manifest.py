#!/usr/bin/env python3
"""Generate the integrity manifest for the entity and relation data layer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path


FILES = (
    ("people.csv", "text/csv"),
    ("institutions.csv", "text/csv"),
    ("places.csv", "text/csv"),
    ("sources.csv", "text/csv"),
    ("relations.csv", "text/csv"),
    ("relation-types.csv", "text/csv"),
    ("entity-graph.jsonld", "application/ld+json"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: inferred from this script).",
    )
    parser.add_argument("--version", default="0.3", help="Dataset version.")
    return parser.parse_args()


def csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def jsonld_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    graph = payload.get("@graph")
    if not isinstance(graph, list):
        raise ValueError(f"{path} has no JSON-LD @graph array")
    return len(graph)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    entity_dir = root / "data" / "entities"

    counts: dict[str, int] = {}
    entries = []
    for name, media_type in FILES:
        path = entity_dir / name
        content = path.read_bytes()
        count = jsonld_count(path) if name.endswith(".jsonld") else csv_count(path)
        counts[name] = count
        entry = {
            "path": f"data/entities/{name}",
            "contentUrl": f"https://milos-timotijevic.github.io/data/entities/{name}",
            "encodingFormat": media_type,
            "byteSize": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "recordCount": count,
        }
        if name.endswith(".jsonld"):
            entry["recordCountDefinition"] = "Number of nodes in @graph"
        entries.append(entry)

    with (root / "data" / "publications.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        publication_ids = {row["id"] for row in csv.DictReader(handle)}
    with (entity_dir / "relations.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        represented_publications = {
            row["source_id"] for row in csv.DictReader(handle) if row["source_id"]
        }
    unknown = represented_publications - publication_ids
    if unknown:
        raise ValueError(f"Unknown publication IDs in relations.csv: {sorted(unknown)}")

    manifest = {
        "schemaVersion": 1,
        "name": "Integrity manifest for the entity and relation data layer",
        "alternateName": "Контролни манифест ентитетско-релационог слоја",
        "version": args.version,
        "dateModified": date.today().isoformat(),
        "algorithm": "SHA-256",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "datasetUrl": "https://milos-timotijevic.github.io/data/entities/",
        "scope": {
            "publications": len(represented_publications),
            "people": counts["people.csv"],
            "institutions": counts["institutions.csv"],
            "places": counts["places.csv"],
            "historicalSources": counts["sources.csv"],
            "relations": counts["relations.csv"],
            "relationTypes": counts["relation-types.csv"],
            "jsonLdNodes": counts["entity-graph.jsonld"],
        },
        "files": entries,
    }

    output = entity_dir / "entity-manifest.json"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote integrity metadata for {len(entries)} files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
