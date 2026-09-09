#!/usr/bin/env python3
"""Validate a Design Graph against the v0.1 JSON Schema and graph integrity rules."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def validate_graph(graph_path: Path, schema_path: Path) -> list[str]:
    graph = load_json(graph_path)
    schema = load_json(schema_path)
    errors: list[str] = []

    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(graph), key=lambda e: list(e.path)):
        loc = ".".join(str(x) for x in err.path) or "<root>"
        errors.append(f"schema:{loc}: {err.message}")

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    id_set = set(ids)

    if len(ids) != len(id_set):
        seen = set()
        duplicates = []
        for x in ids:
            if x in seen and x not in duplicates:
                duplicates.append(x)
            seen.add(x)
        errors.append("integrity: duplicate node ids: " + ", ".join(map(str, duplicates)))

    edge_keys = []
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        frm, rel, to = edge.get("from"), edge.get("relation"), edge.get("to")
        if frm not in id_set:
            errors.append(f"integrity: edge[{i}].from references missing node: {frm}")
        if to not in id_set:
            errors.append(f"integrity: edge[{i}].to references missing node: {to}")
        key = (frm, rel, to)
        edge_keys.append(key)

        evidence = edge.get("evidence") or {}
        if evidence.get("kind") == "inferred" and not evidence.get("rationale"):
            errors.append(f"integrity: edge[{i}] inferred evidence requires rationale")

    if len(edge_keys) != len(set(edge_keys)):
        errors.append("integrity: duplicate edge triples found")

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        evidence = node.get("evidence") or {}
        if evidence.get("kind") == "inferred" and not evidence.get("rationale"):
            errors.append(f"integrity: node[{i}] inferred evidence requires rationale")

    unresolved_ids = [u.get("id") for u in graph.get("unresolved", []) if isinstance(u, dict)]
    if len(unresolved_ids) != len(set(unresolved_ids)):
        errors.append("integrity: duplicate unresolved ids found")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path, help="Path to graph JSON")
    parser.add_argument(
        "--schema",
        type=Path,
        default=repo_root() / "schema" / "design-graph.schema.json",
        help="Path to JSON Schema",
    )
    args = parser.parse_args()

    errors = validate_graph(args.graph, args.schema)
    if errors:
        print(f"FAIL: {args.graph}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"PASS: {args.graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
