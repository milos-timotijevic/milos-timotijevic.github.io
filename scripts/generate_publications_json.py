#!/usr/bin/env python3
"""Generate JSON and JSON-LD bibliography exports from publications.csv."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate data/publications.json from publications.csv."
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

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = [
            {field: (row.get(field, "").strip() or None) for field in fields}
            for row in reader
        ]

    payload = {
        "name": "Open Data of the Digital Scholarly Corpus of Miloš Timotijević",
        "alternateName": "Отворени подаци дигиталног научног корпуса Милоша Тимотијевића",
        "description": "Machine-readable export of verified bibliography records.",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "source": "https://milos-timotijevic.github.io/data/publications.csv",
        "dateModified": date.today().isoformat(),
        "recordCount": len(rows),
        "fields": fields,
        "records": rows,
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(rows)} records to {json_path}")

    type_map = {
        "article": "ScholarlyArticle",
        "book": "Book",
        "book_chapter": "Chapter",
        "chapter": "Chapter",
        "catalogue": "Book",
        "conference-paper": "ScholarlyArticle",
        "conference_abstract": "ScholarlyArticle",
        "conference_paper": "ScholarlyArticle",
    }

    graph = []
    work_ids = []
    for row in rows:
        landing_page = row.get("landing_page")
        work_id = (
            "https://milos-timotijevic.github.io/data/publications.jsonld#"
            f"{row['id']}"
        )
        work_ids.append({"@id": work_id})
        authors = [
            {"@type": "Person", "name": name.strip()}
            for name in (row.get("author_en") or row.get("author_sr") or "").split(";")
            if name.strip()
        ]
        node = {
            "@id": work_id,
            "@type": type_map.get(row.get("type"), "CreativeWork"),
            "identifier": row["id"],
            "name": row.get("title_en") or row.get("title_sr") or row["id"],
            "inLanguage": ["sr", "en"],
        }
        if row.get("title_sr") and row.get("title_en"):
            node["alternateName"] = row["title_sr"]
        if authors:
            node["author"] = authors
        if landing_page:
            node["url"] = landing_page
        if row.get("year"):
            node["datePublished"] = row["year"]
        if row.get("wikidata"):
            node["sameAs"] = f"https://www.wikidata.org/wiki/{row['wikidata']}"
        if row.get("cobiss"):
            node.setdefault("additionalType", "https://schema.org/CreativeWork")
        identifiers = []
        for property_id, key in (
            ("DOI work or edition", "doi_work_or_edition"),
            ("DOI landing page", "doi_landing_page"),
            ("DOI repository", "doi_repository"),
            ("COBISS.SR-ID", "cobiss"),
        ):
            if row.get(key):
                identifiers.append(
                    {
                        "@type": "PropertyValue",
                        "propertyID": property_id,
                        "value": row[key],
                    }
                )
        if identifiers:
            node["identifier"] = [row["id"], *identifiers]
        if row.get("zenodo"):
            node["isBasedOn"] = [
                {"@type": "CreativeWork", "url": url.strip()}
                for url in row["zenodo"].split(";")
                if url.strip()
            ]
        if row.get("cluster"):
            node["about"] = [
                {
                    "@id": "https://milos-timotijevic.github.io/knowledge-graph/"
                    f"research/{cluster.strip()}.html#cluster"
                }
                for cluster in row["cluster"].split(";")
                if cluster.strip()
            ]
        graph.append(node)

    dataset_id = "https://milos-timotijevic.github.io/data/publications.jsonld#dataset"
    jsonld_payload = {
        "@context": {
            "@vocab": "https://schema.org/",
            "schema": "https://schema.org/",
        },
        "@graph": [
            {
                "@id": dataset_id,
                "@type": "Dataset",
                "name": payload["name"],
                "alternateName": payload["alternateName"],
                "url": "https://milos-timotijevic.github.io/data/",
                "license": payload["license"],
                "dateModified": payload["dateModified"],
                "creator": {
                    "@id": "https://milos-timotijevic.github.io/#person"
                },
                "distribution": {
                    "@type": "DataDownload",
                    "encodingFormat": "application/ld+json",
                    "contentUrl": "https://milos-timotijevic.github.io/data/publications.jsonld",
                },
                "hasPart": work_ids,
            },
            *graph,
        ],
    }
    with jsonld_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(jsonld_payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(graph)} Schema.org work nodes to {jsonld_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
