#!/usr/bin/env python3
"""Basic deterministic comparison of a generated Design Graph to a gold graph.

This is intentionally not a replacement for semantic human review.
It measures exact/canonical overlap so regressions and stability drift are visible.
"""

from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SCORER_VERSION = "0.3.0"


def load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def f1(gold: set, pred: set):
    if not gold and not pred:
        return 1.0, 1.0, 1.0
    precision = len(gold & pred) / len(pred) if pred else 0.0
    recall = len(gold & pred) / len(gold) if gold else 1.0
    score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, score


def node_signature(n):
    return (
        n.get("id"),
        n.get("type"),
        n.get("role"),
        n.get("semanticRole"),
        n.get("category"),
    )


def _tokens(n):
    """Lowercased word tokens of a node's human identity (text, else name,
    else last id segment). Basis for drift-tolerant matching (v0.2)."""
    base = n.get("text") or n.get("name") or str(n.get("id", "")).split(".")[-1]
    return frozenset(t for t in re.split(r"[^a-z0-9]+", base.lower()) if t)


def node_concept(n):
    """Normalized concept signature: survives id spelling drift.
    Blind replication showed id-level F1 collapsing on synonyms while the
    underlying concepts agreed; this dimension measures the concepts."""
    return (n.get("type"), _tokens(n))


def uno_mapping_triples(graph):
    """v0.4 Uno mapping layer (references/uno-mapping.md): every
    (node type, uno key, uno value) fact. Values are exact declared strings
    (resource keys, x:Names, control types), so exact-match scoring measures
    the copy-don't-coin contract directly, independent of node ids."""
    out = set()
    for n in graph.get("nodes", []):
        if not isinstance(n, dict):
            continue
        uno = (n.get("properties") or {}).get("uno") or {}
        for k, v in uno.items():
            out.add((n.get("type"), k, str(v)))
    return out


def edge_signature(e):
    return (e.get("from"), e.get("relation"), e.get("to"))


def unresolved_signature(u):
    # Match on the canonical node ids the uncertainty attaches to, not the
    # prose. Two runs that flag the same ambiguity always word the question
    # differently, and exact question matching scored semantically identical
    # unresolved items at 0.0 in repeated runs.
    return tuple(sorted(u.get("relatedIds", [])))


def round4(x):
    return round(float(x), 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gold", type=Path)
    parser.add_argument("generated", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    gold = load(args.gold)
    pred = load(args.generated)

    metrics = {}

    dimensions = {
        "node_id": (
            {n["id"] for n in gold.get("nodes", [])},
            {n["id"] for n in pred.get("nodes", [])},
        ),
        "node_signature": (
            {node_signature(n) for n in gold.get("nodes", [])},
            {node_signature(n) for n in pred.get("nodes", [])},
        ),
        "node_concept": (
            {node_concept(n) for n in gold.get("nodes", [])},
            {node_concept(n) for n in pred.get("nodes", [])},
        ),
        "uno_mapping": (
            uno_mapping_triples(gold),
            uno_mapping_triples(pred),
        ),
        "edge": (
            {edge_signature(e) for e in gold.get("edges", [])},
            {edge_signature(e) for e in pred.get("edges", [])},
        ),
        "unresolved": (
            {unresolved_signature(u) for u in gold.get("unresolved", [])},
            {unresolved_signature(u) for u in pred.get("unresolved", [])},
        ),
    }

    f1s = []
    for name, (g, p) in dimensions.items():
        precision, recall, score = f1(g, p)
        metrics[name] = {
            "precision": round4(precision),
            "recall": round4(recall),
            "f1": round4(score),
            "gold_count": len(g),
            "generated_count": len(p),
        }
        f1s.append(score)

    metrics["macro_f1"] = round4(sum(f1s) / len(f1s))

    # Hallucination proxy (v0.2): a generated behavioral edge is *supported*
    # when gold has an edge with the same relation whose endpoints share
    # identity tokens with the generated endpoints. Exact-triple matching
    # (v0.1) false-flagged every renamed-but-real behavior in blind runs.
    def stems(tokens):
        # Light suffix-stemming so morphological variants match
        # ("Save" vs "Saved", "Clear" vs "Cleared").
        out = set(tokens)
        for t in tokens:
            if t.endswith("ing") and len(t) > 4:
                out.add(t[:-3])
            if t.endswith("ed") and len(t) > 3:
                out.add(t[:-2])
                out.add(t[:-1])
            if t.endswith("s") and len(t) > 3:
                out.add(t[:-1])
        return frozenset(out)

    def behavior_edges(graph):
        nodes = {n.get("id"): n for n in graph.get("nodes", []) if isinstance(n, dict)}
        out = []
        for e in graph.get("edges", []):
            if e.get("relation") in {"navigates-to", "triggers"}:
                out.append((
                    e.get("relation"),
                    stems(_tokens(nodes.get(e.get("from"), {"id": e.get("from")}))),
                    stems(_tokens(nodes.get(e.get("to"), {"id": e.get("to")}))),
                    edge_signature(e),
                ))
        return out

    gold_behavior = behavior_edges(gold)
    unsupported_behavior = []
    for rel, ftok, ttok, sig in behavior_edges(pred):
        supported = any(
            rel == grel and (ftok & gftok) and (ttok & gttok)
            for grel, gftok, gttok, _ in gold_behavior
        )
        if not supported:
            unsupported_behavior.append(sig)
    unsupported_behavior.sort()
    metrics["unsupported_behavior_edges"] = unsupported_behavior
    metrics["severe_hallucination_proxy"] = bool(unsupported_behavior)
    metrics["scorer_version"] = SCORER_VERSION

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Macro F1: {metrics['macro_f1']:.4f}")
        for name in ("node_id", "node_signature", "node_concept", "uno_mapping", "edge", "unresolved"):
            m = metrics[name]
            print(
                f"{name:16} "
                f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} "
                f"(gold={m['gold_count']}, generated={m['generated_count']})"
            )
        if unsupported_behavior:
            print("WARNING: unsupported behavior edges:")
            for edge in unsupported_behavior:
                print("  -", edge)


if __name__ == "__main__":
    main()
