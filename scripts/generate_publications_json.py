#!/usr/bin/env python3
"""Generate data/publications.json from data/publications.csv."""

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
