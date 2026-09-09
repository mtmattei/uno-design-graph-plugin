"""Stdlib-only tests for the Design Graph scripts. Run: python3 -m unittest discover -s scripts/tests"""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
EXAMPLE = ROOT.parent.parent / "examples" / "orbital-settings.graph.json"
sys.path.insert(0, str(SCRIPTS))

import lint_graph  # noqa: E402
import diff_graph  # noqa: E402
from validate_graph import validate_graph  # noqa: E402

SCHEMA = ROOT / "schema" / "design-graph.schema.json"


def load_example() -> dict:
    with EXAMPLE.open(encoding="utf-8") as f:
        return json.load(f)


def node(g, nid):
    return next(n for n in g["nodes"] if n["id"] == nid)


def errors_of(g, rule):
    return [e for e in lint_graph.lint(g).errors if e.startswith(rule + ":")]


def warnings_of(g, rule):
    return [w for w in lint_graph.lint(g).warnings if w.startswith(rule + ":")]


class ExampleIsClean(unittest.TestCase):
    def test_example_validates(self):
        self.assertEqual(validate_graph(EXAMPLE, SCHEMA), [])

    def test_example_lints_clean(self):
        r = lint_graph.lint(load_example())
        self.assertEqual(r.errors, [])
        self.assertEqual(r.warnings, [])

    def test_cli_exit_codes(self):
        for script in ("validate_graph.py", "lint_graph.py"):
            p = subprocess.run([sys.executable, str(SCRIPTS / script), str(EXAMPLE)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class SchemaGating(unittest.TestCase):
    def _write(self, g):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".graph.json", delete=False, encoding="utf-8")
        json.dump(g, f)
        f.close()
        return Path(f.name)

    def test_uno_typo_fails_on_0_2_0(self):
        g = load_example()
        node(g, "control.profile.save")["properties"]["uno"]["xname"] = "Oops"
        errs = validate_graph(self._write(g), SCHEMA)
        self.assertTrue(any("xname" in e for e in errs), errs)

    def test_uno_typo_passes_on_legacy(self):
        g = load_example()
        g["schemaVersion"] = "0.1.0"
        node(g, "control.profile.save")["properties"]["uno"]["xname"] = "Oops"
        self.assertEqual(validate_graph(self._write(g), SCHEMA), [])

    def test_xmlns_prefix_in_type_fails(self):
        g = load_example()
        node(g, "control.profile.save")["properties"]["uno"]["type"] = "utu:Button"
        errs = validate_graph(self._write(g), SCHEMA)
        self.assertTrue(any("utu:Button" in e for e in errs), errs)


class LintRules(unittest.TestCase):
    def test_per_instance_token_edge(self):
        g = load_example()
        g["edges"].append({"from": "component.info-row.platform", "relation": "uses-token", "to": "token.radius.12",
                           "evidence": {"kind": "derived", "confidence": 1.0}})
        self.assertEqual(len(errors_of(g, "token-per-instance")), 1)
        g["edges"][-1]["properties"] = {"override": True}
        self.assertEqual(errors_of(g, "token-per-instance"), [])

    def test_inferred_behavior_edge(self):
        g = load_example()
        g["nodes"].append({"id": "screen.about", "type": "screen", "name": "About",
                           "evidence": {"kind": "inferred", "confidence": 0.8, "rationale": "guess"}})
        g["edges"].append({"from": "control.profile.save", "relation": "navigates-to", "to": "screen.about",
                           "evidence": {"kind": "inferred", "confidence": 0.8, "rationale": "guess"}})
        self.assertEqual(len(errors_of(g, "behavior-inferred")), 1)

    def test_confidence_floor(self):
        g = load_example()
        node(g, "component.info-row")["evidence"] = {"kind": "inferred", "confidence": 0.4, "rationale": "x"}
        self.assertEqual(len(errors_of(g, "confidence-floor")), 1)
        node(g, "component.info-row")["evidence"]["confidence"] = 0.6
        self.assertEqual(errors_of(g, "confidence-floor"), [])
        self.assertEqual(len(warnings_of(g, "confidence-ambiguous")), 1)

    def test_style_level_state(self):
        g = load_example()
        g["nodes"].append({"id": "state.profile.pointerover", "type": "state", "name": "PointerOver",
                           "evidence": {"kind": "declared", "confidence": 1.0}})
        g["edges"].append({"from": "control.profile.save", "relation": "has-state", "to": "state.profile.pointerover",
                           "evidence": {"kind": "declared", "confidence": 1.0}})
        self.assertEqual(len(errors_of(g, "state-style-level")), 1)

    def test_unattached_state_and_unconsumed_token(self):
        g = load_example()
        g["edges"] = [e for e in g["edges"] if e["to"] not in ("state.profile.saved", "token.radius.12")]
        self.assertEqual(len(errors_of(g, "state-unattached")), 1)
        self.assertEqual(len(errors_of(g, "token-unconsumed")), 1)

    def test_design_system_graph_allows_unconsumed_tokens(self):
        g = load_example()
        g["metadata"]["kind"] = "design-system"
        g["edges"] = [e for e in g["edges"] if e["to"] != "token.radius.12"]
        self.assertEqual(errors_of(g, "token-unconsumed"), [])

    def test_relation_domain(self):
        g = load_example()
        g["edges"].append({"from": "screen.settings", "relation": "contains", "to": "token.radius.12",
                           "evidence": {"kind": "declared", "confidence": 1.0}})
        self.assertEqual(len(errors_of(g, "relation-domain")), 1)

    def test_id_grammar(self):
        g = load_example()
        n = node(g, "region.settings.content")
        for e in g["edges"]:
            for k in ("from", "to"):
                if e[k] == n["id"]:
                    e[k] = "region.settings-content"
        n["id"] = "region.settings-content"
        self.assertEqual(len(errors_of(g, "id-grammar")), 1)

    def test_unresolved_ref(self):
        g = load_example()
        g["unresolved"][0]["relatedIds"] = ["control.nope.nope"]
        self.assertEqual(len(errors_of(g, "unresolved-ref")), 1)

    def test_contains_cycle(self):
        g = load_example()
        g["edges"].append({"from": "region.settings.content", "relation": "contains", "to": "screen.settings",
                           "evidence": {"kind": "declared", "confidence": 1.0}})
        r = lint_graph.lint(g)
        self.assertTrue(any(e.startswith("contains-cycle:") or e.startswith("relation-domain:") for e in r.errors))

    def test_instance_internals_only_when_canonical_declares_parts(self):
        g = load_example()
        # settings-card declares no parts: instances may contain content -> no warning
        self.assertEqual(warnings_of(g, "instance-internals"), [])
        node(g, "component.settings-card").setdefault("properties", {})["parts"] = ["title", "body"]
        self.assertTrue(warnings_of(g, "instance-internals"))


class Diff(unittest.TestCase):
    def test_identical_is_clean(self):
        g = load_example()
        d = diff_graph.diff(g, copy.deepcopy(g), only_mapped=True)
        self.assertFalse(d["drift"])
        self.assertEqual(d["extra"], [])

    def test_renamed_node_id_with_same_xname_is_not_drift(self):
        g, h = load_example(), load_example()
        n = node(h, "control.profile.save")
        for e in h["edges"]:
            for k in ("from", "to"):
                if e[k] == n["id"]:
                    e[k] = "control.profile.commit"
        n["id"] = "control.profile.commit"
        self.assertFalse(diff_graph.diff(g, h, only_mapped=True)["drift"])

    def test_changed_style_key_is_drift(self):
        g, h = load_example(), load_example()
        node(h, "control.profile.save")["properties"]["uno"]["styleKey"] = "OrbitalSecondaryButtonSm"
        d = diff_graph.diff(g, h, only_mapped=True)
        self.assertTrue(d["drift"])
        self.assertEqual(d["changed"][0]["key"], "styleKey")

    def test_dropped_xname_reads_as_changed(self):
        g, h = load_example(), load_example()
        del node(h, "control.profile.save")["properties"]["uno"]["xName"]
        d = diff_graph.diff(g, h, only_mapped=True)
        self.assertEqual(d["missing"], [])
        self.assertEqual([c["key"] for c in d["changed"]], ["xName"])

    def test_missing_resource_key(self):
        g, h = load_example(), load_example()
        h["nodes"] = [n for n in h["nodes"] if n["id"] != "token.color.surface1"]
        h["edges"] = [e for e in h["edges"] if e["to"] != "token.color.surface1"]
        d = diff_graph.diff(g, h, only_mapped=True)
        self.assertEqual([m["id"] for m in d["missing"]], ["token.color.surface1"])


class Score(unittest.TestCase):
    def run_score(self, gold, pred, *flags):
        import tempfile
        paths = []
        for g in (gold, pred):
            f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(g, f)
            f.close()
            paths.append(f.name)
        p = subprocess.run([sys.executable, str(SCRIPTS / "score_graph.py"), *paths, "--json", *flags],
                           capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout)

    def test_self_score_is_perfect(self):
        g = load_example()
        code, m = self.run_score(g, g)
        self.assertEqual(code, 0)
        self.assertEqual(m["macro_f1"], 1.0)

    def test_unresolved_overlap_matching(self):
        g, h = load_example(), load_example()
        h["unresolved"][0]["relatedIds"] = ["control.header.search", "component.page-header"]
        _, m = self.run_score(g, h)
        self.assertEqual(m["unresolved"]["f1"], 1.0)

    def test_fail_on_hallucination(self):
        g, h = load_example(), load_example()
        h["nodes"].append({"id": "screen.about", "type": "screen", "name": "About",
                           "evidence": {"kind": "inferred", "confidence": 0.8, "rationale": "x"}})
        h["edges"].append({"from": "control.profile.save", "relation": "navigates-to", "to": "screen.about",
                           "evidence": {"kind": "inferred", "confidence": 0.8, "rationale": "x"}})
        code, m = self.run_score(g, h, "--fail-on-hallucination")
        self.assertEqual(code, 1)
        self.assertTrue(m["severe_hallucination_proxy"])


if __name__ == "__main__":
    unittest.main()
