#!/usr/bin/env python3
"""Validate the site's core JSON-LD knowledge graph."""

import json
import re
from pathlib import Path
import sys
from urllib.parse import urlparse


SITE = "https://milos-timotijevic.github.io/"
REQUIRED_IDS = {
    f"{SITE}#person": "Person",
    f"{SITE}#website": "WebSite",
    f"{SITE}knowledge-graph/#page": "CollectionPage",
    f"{SITE}data/#dataset": "Dataset",
}
REQUIRED_PERSON_IDENTIFIERS = (
    "https://orcid.org/",
    "https://www.wikidata.org/wiki/",
    "https://openalex.org/",
)
WIKIDATA_ITEM_RE = re.compile(r"^https://www\.wikidata\.org/wiki/Q\d+$")


def collect_referenced_ids(value):
    references = []
    if isinstance(value, dict):
        if set(value) == {"@id"} and isinstance(value["@id"], str):
            references.append(value["@id"])
        for child in value.values():
            references.extend(collect_referenced_ids(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(collect_referenced_ids(child))
    return references


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def is_absolute_http_url(value):
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main() -> int:
    graph_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "data/knowledge-graph.jsonld"
    )
    errors = []

    if not graph_path.is_file():
        print(f"ERROR: Knowledge graph file not found: {graph_path}")
        return 1

    try:
        document = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot read valid UTF-8 JSON-LD: {exc}")
        return 1

    context = document.get("@context")
    if not isinstance(context, (dict, list, str)):
        errors.append("The document must define a JSON-LD @context.")

    graph = document.get("@graph")
    if not isinstance(graph, list) or not graph:
        errors.append("The document must contain a non-empty @graph array.")
        graph = []

    nodes = {}
    for position, node in enumerate(graph, start=1):
        if not isinstance(node, dict):
            errors.append(f"Graph item {position} is not an object.")
            continue
        node_id = node.get("@id")
        node_type = node.get("@type")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"Graph item {position} has no non-empty @id.")
            continue
        if node_id in nodes:
            errors.append(f"Duplicate @id: {node_id}")
        nodes[node_id] = node
        if not isinstance(node_type, (str, list)):
            errors.append(f"{node_id}: missing @type.")
        if not urlparse(node_id).scheme:
            errors.append(f"{node_id}: @id must be an absolute URL.")

    for node_id, required_type in REQUIRED_IDS.items():
        node = nodes.get(node_id)
        if node is None:
            errors.append(f"Required node is missing: {node_id}")
        elif required_type not in (
            [node.get("@type")]
            if isinstance(node.get("@type"), str)
            else node.get("@type", [])
        ):
            errors.append(f"{node_id}: expected @type {required_type}.")

    person = nodes.get(f"{SITE}#person", {})
    same_as = as_list(person.get("sameAs"))
    for prefix in REQUIRED_PERSON_IDENTIFIERS:
        if not any(
            isinstance(identifier, str) and identifier.startswith(prefix)
            for identifier in same_as
        ):
            errors.append(f"Person node lacks an identifier beginning with {prefix}")

    for reference in collect_referenced_ids(document):
        if reference.startswith(SITE) and reference not in nodes:
            errors.append(f"Unresolved internal @id reference: {reference}")

    for node_id, node in nodes.items():
        node_type = node.get("@type")
        types = [node_type] if isinstance(node_type, str) else node_type or []
        if "DefinedTerm" not in types:
            continue

        public_url = node.get("url")
        if not is_absolute_http_url(public_url):
            errors.append(f"{node_id}: DefinedTerm lacks a valid public url.")

        # Local analytical concepts are valid first-class nodes even when no
        # external authority item exists. sameAs is optional; when supplied,
        # its values must be valid absolute URLs, with strict Wikidata syntax.
        for identifier in as_list(node.get("sameAs")):
            if not is_absolute_http_url(identifier):
                errors.append(
                    f"{node_id}: DefinedTerm sameAs is not an absolute URL: {identifier!r}"
                )
            elif "wikidata.org" in identifier and not WIKIDATA_ITEM_RE.match(identifier):
                errors.append(f"{node_id}: invalid Wikidata sameAs URL: {identifier}")

    if errors:
        print("Knowledge graph validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    defined_terms = sum(
        "DefinedTerm" in (
            [node.get("@type")]
            if isinstance(node.get("@type"), str)
            else node.get("@type", [])
        )
        for node in nodes.values()
    )
    print(
        f"Knowledge graph validation passed: {len(nodes)} unique nodes, "
        f"{defined_terms} DefinedTerm nodes with public URLs, core entities and "
        "identity links are present, and internal references resolve."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
