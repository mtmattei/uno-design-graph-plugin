#!/usr/bin/env python3
"""Lint a Design Graph against the binding rules in references/.

validate_graph.py checks the schema and referential integrity. This script
checks the rules that came out of measured blind-run failures and used to
live only in prose: ID grammar, relation domains, token-edge attachment,
state altitude, confidence thresholds, behavior-edge evidence, token scope,
and unresolved references.

Exit code 1 on any error. Warnings never fail the run unless --strict.
"""

from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

LINT_VERSION = "0.1.0"

NODE_TYPES = {"screen", "region", "component", "control", "content", "asset", "token", "state"}
BEHAVIOR = {"navigates-to", "triggers"}

# relation -> (allowed from types, allowed to types)
DOMAINS = {
    "contains": ({"screen", "region", "component", "control"},
                 {"region", "component", "control", "content", "asset"}),
    "instance-of": ({"component"}, {"component"}),
    "variant-of": ({"component"}, {"component"}),
    "uses-token": ({"screen", "region", "component", "control", "content", "asset"}, {"token"}),
    "has-state": ({"screen", "region", "component", "control"}, {"state"}),
    "navigates-to": ({"control", "component"}, {"screen"}),
    "triggers": ({"control", "component"}, {"state", "component", "screen"}),
}

STYLE_STATE_WORDS = {"pointerover", "pointer-over", "hover", "hovered", "pressed", "focused", "focus"}
GENERIC_SCREEN_SLUGS = {"main", "home", "index", "shell", "page"}
SEGMENT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, rule: str, msg: str):
        self.errors.append(f"{rule}: {msg}")

    def warn(self, rule: str, msg: str):
        self.warnings.append(f"{rule}: {msg}")


def _segments(node_id: str) -> list[str]:
    return node_id.split(".")


def lint(graph: dict) -> Report:
    r = Report()
    nodes = [n for n in graph.get("nodes", []) if isinstance(n, dict)]
    edges = [e for e in graph.get("edges", []) if isinstance(e, dict)]
    by_id = {n.get("id"): n for n in nodes}
    kind = (graph.get("metadata") or {}).get("kind", "screen")

    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for e in edges:
        incoming[e.get("to")].append(e)
        outgoing[e.get("from")].append(e)

    instance_ids = {e["from"] for e in edges if e.get("relation") == "instance-of"}
    canonical_ids = {e["to"] for e in edges if e.get("relation") == "instance-of"}

    # --- ID grammar (method.md Pass 8) ---
    for n in nodes:
        nid, t = n.get("id", ""), n.get("type")
        segs = _segments(nid)
        if segs[0] != t:
            r.error("id-prefix", f"{nid}: first segment must equal node type '{t}'")
        bad = [s for s in segs if not SEGMENT.match(s)]
        if bad:
            r.error("id-segment", f"{nid}: segments must be lowercase slugs with hyphens inside a segment (bad: {bad})")
        if t == "screen":
            if len(segs) != 2:
                r.error("id-screen", f"{nid}: screen ids are 'screen.<slug>' (2 segments)")
            elif segs[1] in GENERIC_SCREEN_SLUGS:
                r.warn("id-screen-generic", f"{nid}: generic screen slug; prefix the app slug (e.g. screen.caffe-main)")
        elif t == "component":
            if len(segs) == 2:
                pass  # canonical
            elif len(segs) == 3:
                if nid not in instance_ids:
                    r.warn("id-component-instance", f"{nid}: 3-segment component id but no instance-of edge; canonical components are 2 segments")
            else:
                r.error("id-component", f"{nid}: component ids are 'component.<slug>' or 'component.<canonical>.<instance>'")
        else:
            if len(segs) != 3:
                r.error("id-grammar", f"{nid}: '{t}' ids are '<type>.<scope>.<element>' (exactly 3 segments)")

    # --- relation domains (ontology.md) ---
    for i, e in enumerate(edges):
        rel, f, t = e.get("relation"), e.get("from"), e.get("to")
        fn, tn = by_id.get(f), by_id.get(t)
        if not fn or not tn or rel not in DOMAINS:
            continue  # validate_graph.py reports missing nodes / unknown relations
        allowed_from, allowed_to = DOMAINS[rel]
        if fn.get("type") not in allowed_from:
            r.error("relation-domain", f"edge[{i}] {f} -{rel}-> {t}: '{rel}' cannot start from a {fn.get('type')}")
        if tn.get("type") not in allowed_to:
            r.error("relation-domain", f"edge[{i}] {f} -{rel}-> {t}: '{rel}' cannot point to a {tn.get('type')}")
        if rel == "instance-of" and len(_segments(t)) != 2:
            r.error("instance-of-canonical", f"edge[{i}]: instance-of must target a canonical component (2-segment id), got {t}")
        if f == t:
            r.error("self-edge", f"edge[{i}]: {f} -{rel}-> {t}")

    # --- contains must be a tree without cycles ---
    children = defaultdict(list)
    parents = defaultdict(list)
    for e in edges:
        if e.get("relation") == "contains":
            children[e["from"]].append(e["to"])
            parents[e["to"]].append(e["from"])
    for cid, ps in parents.items():
        if len(ps) > 1:
            r.error("contains-multiparent", f"{cid} is contained by {len(ps)} nodes: {ps}")
    visiting, done = set(), set()

    def visit(n, path):
        if n in done:
            return
        if n in visiting:
            r.error("contains-cycle", " -> ".join(path + [n]))
            return
        visiting.add(n)
        for c in children.get(n, []):
            visit(c, path + [n])
        visiting.discard(n)
        done.add(n)

    for root in list(children):
        visit(root, [])

    # --- token-edge attachment (token-rules.md, Attachment) ---
    for i, e in enumerate(edges):
        if e.get("relation") != "uses-token":
            continue
        f = e.get("from")
        if f in instance_ids and not (e.get("properties") or {}).get("override"):
            r.error("token-per-instance",
                    f"edge[{i}] {f} -uses-token-> {e.get('to')}: instances inherit the canonical's tokens; "
                    "attach to the canonical, or set properties.override=true if this instance overrides it")

    # --- canonical internals (method.md Pass 3) ---
    # A canonical that declares properties.parts has a fixed internal
    # structure: its instances must not re-model those parts as child nodes.
    # A canonical without parts (a card, a section) is a container concept
    # whose instances legitimately contain their own content.
    def canonical_of(instance_id):
        return next((x["to"] for x in outgoing[instance_id] if x.get("relation") == "instance-of"), None)

    for e in edges:
        if e.get("relation") != "contains":
            continue
        f, t = e.get("from"), e.get("to")
        if f in canonical_ids and by_id.get(t, {}).get("type") in {"content", "asset", "control"}:
            r.warn("canonical-internals",
                   f"{f} contains {t}: an instanced canonical's internal parts belong in properties.parts, not child nodes")
        if f in instance_ids and not (e.get("properties") or {}).get("override"):
            canon = by_id.get(canonical_of(f) or "", {})
            if (canon.get("properties") or {}).get("parts"):
                r.warn("instance-internals",
                       f"{f} contains {t}: the canonical declares parts; instances carry only what differs. "
                       "Mark properties.override=true if this is a genuine override")

    # --- state altitude (ontology.md, Scope rule) ---
    for n in nodes:
        if n.get("type") != "state":
            continue
        words = set(re.split(r"[^a-z0-9-]+", (n.get("name") or "").lower())) | {_segments(n["id"])[-1]}
        if words & STYLE_STATE_WORDS:
            r.error("state-style-level", f"{n['id']}: PointerOver/Pressed/Focused are style internals, not screen states")
        if not any(e.get("relation") == "has-state" for e in incoming[n["id"]]):
            r.error("state-unattached", f"{n['id']}: no has-state edge points at this state")

    # --- token scope (token-rules.md, Scope) ---
    for n in nodes:
        if n.get("type") != "token":
            continue
        if kind == "screen" and not any(e.get("relation") == "uses-token" for e in incoming[n["id"]]):
            r.error("token-unconsumed", f"{n['id']}: no uses-token edge; screen graphs only carry tokens the surface consumes")
        if not n.get("category"):
            r.error("token-category", f"{n['id']}: token nodes need a category")

    # --- confidence thresholds (inference-rules.md) ---
    def check_evidence(owner: str, ev: dict):
        kind_, conf = ev.get("kind"), ev.get("confidence")
        if kind_ == "inferred":
            if conf is None:
                return
            if conf < 0.55:
                r.error("confidence-floor", f"{owner}: inferred at {conf}; below 0.55 goes in unresolved, not the graph")
            elif conf < 0.75:
                r.warn("confidence-ambiguous", f"{owner}: inferred at {conf}; plausible but ambiguous, consider unresolved")
            elif conf >= 1.0:
                r.warn("confidence-inferred-certain", f"{owner}: inferred at 1.0; an inference is never a certainty")
        elif kind_ in {"observed", "declared"} and conf is not None and conf < 0.9:
            r.warn("confidence-low-fact", f"{owner}: {kind_} evidence at {conf}; observed/declared facts are normally 1.0")

    for n in nodes:
        check_evidence(n["id"], n.get("evidence") or {})
    for i, e in enumerate(edges):
        check_evidence(f"edge[{i}] {e.get('from')} -{e.get('relation')}-> {e.get('to')}", e.get("evidence") or {})

    # --- behavior edges need declared/observed/derived evidence (method.md Pass 7) ---
    for i, e in enumerate(edges):
        if e.get("relation") not in BEHAVIOR:
            continue
        ev = e.get("evidence") or {}
        label = f"edge[{i}] {e.get('from')} -{e.get('relation')}-> {e.get('to')}"
        if ev.get("kind") == "inferred":
            r.error("behavior-inferred", f"{label}: behavior edges require source code, runtime, or explicit user evidence; never inference")
        if (ev.get("source") or {}).get("type") == "screenshot":
            r.error("behavior-from-screenshot", f"{label}: a screenshot cannot evidence behavior")

    # --- trigger attachment: canonical vs per-instance (ontology.md v0.5) ---
    trig_by_target = defaultdict(set)
    for e in edges:
        if e.get("relation") == "triggers" and e.get("from") in instance_ids:
            canon = next((x["to"] for x in outgoing[e["from"]] if x.get("relation") == "instance-of"), None)
            trig_by_target[(canon, e.get("to"))].add(e["from"])
    for (canon, target), insts in trig_by_target.items():
        if len(insts) > 1:
            r.warn("trigger-per-instance", f"{len(insts)} instances of {canon} trigger {target}; attach once from the canonical")

    # --- unresolved references ---
    for u in graph.get("unresolved", []) or []:
        if not isinstance(u, dict):
            continue
        for rid in u.get("relatedIds", []):
            if rid not in by_id:
                r.error("unresolved-ref", f"{u.get('id')}: relatedIds references missing node {rid}")

    # --- orphans ---
    for n in nodes:
        nid = n["id"]
        if n.get("type") != "screen" and not incoming[nid] and not outgoing[nid]:
            r.warn("orphan", f"{nid}: no edges")

    # --- screen count ---
    screens = [n for n in nodes if n.get("type") == "screen"]
    if kind == "screen" and not screens:
        r.warn("no-screen", "screen graph has no screen node")
    if kind == "screen" and len(screens) > 1:
        r.warn("multi-screen", f"{len(screens)} screens in one screen graph; navigates-to targets are normally stubs or separate graphs")

    return r


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    with args.graph.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    report = lint(graph)
    failed = bool(report.errors) or (args.strict and bool(report.warnings))

    if args.json:
        print(json.dumps({"lint_version": LINT_VERSION, "errors": report.errors,
                          "warnings": report.warnings, "ok": not failed}, indent=2))
    else:
        print(f"{'FAIL' if failed else 'PASS'}: {args.graph} ({len(report.errors)} errors, {len(report.warnings)} warnings)")
        for e in report.errors:
            print(f"  E {e}")
        for w in report.warnings:
            print(f"  W {w}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
