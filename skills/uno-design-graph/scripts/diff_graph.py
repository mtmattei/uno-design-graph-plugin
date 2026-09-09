#!/usr/bin/env python3
"""Report Uno-layer drift between two Design Graphs.

The round-trip contract (references/uno-mapping.md, rule 4) says
design -> graph -> implementation -> graph must preserve uno.type, uno.xName,
uno.styleKey, and uno.resourceKey exactly. This script makes that
executable: give it the design graph and a graph built from the running
app (references/runtime-source.md) and it lists every identity that
changed, disappeared, or appeared.

Nodes are matched by identity, in this order: uno.xName, uno.resourceKey,
uno.class, then node id. Matching on declared identity first means a
renamed node id is not reported as drift when the XAML identity survived.

Exit code 1 when any drift is found.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

DIFF_VERSION = "0.1.0"
IDENTITY_KEYS = ("xName", "resourceKey", "class")
COMPARED_KEYS = ("type", "namespace", "xName", "styleKey", "resourceKey", "resourceType", "class", "mechanism", "member")


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def uno_of(n: dict) -> dict:
    return (n.get("properties") or {}).get("uno") or {}


def identity(n: dict):
    u = uno_of(n)
    for k in IDENTITY_KEYS:
        if u.get(k):
            return (n.get("type"), k, u[k])
    return (n.get("type"), "id", n.get("id"))


def index(graph: dict) -> dict:
    out = {}
    for n in graph.get("nodes", []):
        if isinstance(n, dict):
            out.setdefault(identity(n), n)
    return out


def diff(expected: dict, actual: dict, only_mapped: bool) -> dict:
    exp, act = index(expected), index(actual)
    missing, extra, changed = [], [], []
    matched_actual = set()

    def compare(key, n, m):
        eu, au = uno_of(n), uno_of(m)
        for k in COMPARED_KEYS:
            if k in eu and eu.get(k) != au.get(k):
                changed.append({"identity": list(key), "id": n.get("id"), "key": k,
                                "expected": eu.get(k), "actual": au.get(k)})

    # Pass 1: declared identity (xName / resourceKey / class), then id.
    unmatched_exp = []
    for key, n in exp.items():
        if only_mapped and not uno_of(n):
            continue
        m = act.get(key)
        if m is None:
            unmatched_exp.append((key, n))
            continue
        matched_actual.add(id(m))
        compare(key, n, m)

    # Pass 2: fall back to node id for what is left, so a dropped or
    # renamed xName reads as "changed", not as missing plus extra.
    by_actual_id = {m.get("id"): m for m in act.values() if id(m) not in matched_actual}
    for key, n in unmatched_exp:
        m = by_actual_id.get(n.get("id"))
        if m is None:
            missing.append({"identity": list(key), "id": n.get("id")})
            continue
        matched_actual.add(id(m))
        compare(key, n, m)

    for key, m in act.items():
        if id(m) not in matched_actual and (uno_of(m) or not only_mapped):
            extra.append({"identity": list(key), "id": m.get("id")})
    return {"diff_version": DIFF_VERSION, "missing": missing, "extra": extra, "changed": changed,
            "drift": bool(missing or changed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("expected", type=Path, help="Design graph (source of truth)")
    parser.add_argument("actual", type=Path, help="Graph built from the implementation or the running app")
    parser.add_argument("--all-nodes", action="store_true",
                        help="Also report nodes with no uno layer (default: only mapped nodes)")
    parser.add_argument("--fail-on-extra", action="store_true",
                        help="Also fail when the actual graph carries mapped nodes the design graph lacks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = diff(load(args.expected), load(args.actual), only_mapped=not args.all_nodes)
    failed = result["drift"] or (args.fail_on_extra and bool(result["extra"]))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{'DRIFT' if failed else 'OK'}: {len(result['missing'])} missing, "
              f"{len(result['changed'])} changed, {len(result['extra'])} extra")
        for m in result["missing"]:
            print(f"  - missing  {m['id']}  ({m['identity'][1]}={m['identity'][2]})")
        for c in result["changed"]:
            print(f"  ~ changed  {c['id']}  uno.{c['key']}: {c['expected']!r} -> {c['actual']!r}")
        for x in result["extra"]:
            print(f"  + extra    {x['id']}  ({x['identity'][1]}={x['identity'][2]})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
