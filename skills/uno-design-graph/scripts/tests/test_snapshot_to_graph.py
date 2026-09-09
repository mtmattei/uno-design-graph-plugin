"""Stdlib-only tests for snapshot_to_graph.py. Run: python3 -m unittest discover -s scripts/tests

The fixture is RECONSTRUCTED from the line grammar the App MCP server publishes in the
uno_app_visualtree_snapshot tool description (Uno.UI.App.Mcp 1.3.4), using the identities of
examples/orbital-settings.graph.json. It is not a capture from a running app.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
EXAMPLE = ROOT.parent.parent / "examples" / "orbital-settings.graph.json"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "orbital-settings.reconstructed.snapshot.txt"
SCHEMA = ROOT / "schema" / "design-graph.schema.json"
sys.path.insert(0, str(SCRIPTS))

import diff_graph  # noqa: E402
import lint_graph  # noqa: E402
import snapshot_to_graph as s2g  # noqa: E402
from validate_graph import validate_graph  # noqa: E402


def build(text: str | None = None, **kwargs) -> dict:
    text = FIXTURE.read_text(encoding="utf-8") if text is None else text
    roots = s2g.parse_snapshot(text)
    return s2g.build_graph(roots, kwargs.get("graph_id"), kwargs.get("screen_slug"),
                           kwargs.get("include_lib", False), kwargs.get("design"))


def node(g: dict, nid: str) -> dict:
    return next(n for n in g["nodes"] if n["id"] == nid)


def by_xname(g: dict, x: str) -> dict:
    return next(n for n in g["nodes"] if n["properties"]["uno"].get("xName") == x)


def write_tmp(g: dict) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".graph.json", delete=False, encoding="utf-8")
    json.dump(g, f)
    f.close()
    return Path(f.name)


class Parsing(unittest.TestCase):
    def test_scope_line_becomes_screen_with_kind_and_datacontext(self):
        g = build()
        screen = node(g, "screen.settings")
        self.assertEqual(screen["properties"]["uno"], {"type": "Page"})
        self.assertEqual(screen["properties"]["dataContextType"], "SettingsViewModel")
        self.assertEqual(screen["evidence"]["locator"]["file"], "Presentation/SettingsPage.xaml")
        self.assertEqual(screen["evidence"]["source"]["type"], "runtime")

    def test_nested_scope_becomes_component_and_scopes_line_numbers(self):
        g = build()
        header = node(g, "component.page-header")
        self.assertEqual(header["properties"]["uno"], {"type": "UserControl"})
        image = next(n for n in g["nodes"] if n["properties"]["uno"]["type"] == "Image")
        self.assertEqual(image["evidence"]["locator"]["file"], "Controls/PageHeader.xaml")
        self.assertEqual(image["evidence"]["locator"]["line"], 11)
        parent_of = {e["to"]: e["from"] for e in g["edges"] if e["relation"] == "contains"}
        inner_grid = parent_of[image["id"]]
        self.assertEqual(parent_of[inner_grid], "component.page-header")
        self.assertEqual(parent_of["component.page-header"], "region.settings.grid-12")

    def test_xname_is_copied_verbatim_and_type_has_no_prefix(self):
        g = build()
        save = by_xname(g, "SaveUsernameButton")
        self.assertEqual(save["properties"]["uno"], {"type": "Button", "xName": "SaveUsernameButton"})
        self.assertEqual(save["text"], "Save")
        self.assertEqual(save["properties"]["automationPatterns"], ["i"])
        self.assertEqual(save["evidence"]["locator"]["line"], 31)

    def test_non_identifier_name_is_not_an_xname(self):
        g = build()
        status = next(n for n in g["nodes"] if n["properties"].get("automationName") == "status-message")
        self.assertNotIn("xName", status["properties"]["uno"])
        self.assertEqual(status["tags"], ["hidden"])

    def test_bindings_bounds_opacity_transform(self):
        g = build()
        box = by_xname(g, "UsernameBox")
        self.assertEqual(box["properties"]["bindings"], [{"property": "Text", "path": "Username", "mode": "2way"}])
        row = next(n for n in g["nodes"] if n["properties"].get("dataContextType") == "AboutRow")
        self.assertEqual(row["geometry"], {"x": 16.0, "y": 412.0, "width": 328.0, "height": 24.0, "unit": "px"})
        self.assertEqual(row["properties"]["opacity"], 0.5)
        self.assertTrue(row["properties"]["renderTransform"])

    def test_lib_nodes_dropped_by_default_and_kept_on_request(self):
        g = build()
        self.assertFalse(any(n["properties"]["uno"]["type"] == "ContentPresenter" for n in g["nodes"]))
        h = build(include_lib=True)
        cp = next(n for n in h["nodes"] if n["properties"]["uno"]["type"] == "ContentPresenter")
        self.assertEqual(cp["tags"], ["lib"])

    def test_code_node_is_tagged_and_has_no_line(self):
        g = build()
        rect = next(n for n in g["nodes"] if n["properties"]["uno"]["type"] == "Rectangle")
        self.assertEqual(rect["tags"], ["code"])
        self.assertNotIn("line", rect["evidence"]["locator"])

    def test_ids_are_unique_and_follow_grammar(self):
        g = build()
        ids = [n["id"] for n in g["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for n in g["nodes"]:
            self.assertEqual(n["id"].split(".")[0], n["type"])

    def test_usercontrol_as_element_line_plus_scope_line_is_one_node(self):
        text = (
            "@ Views/MainPage.xaml ^0  (Page)\n"
            "  Grid ^1 :3\n"
            "    PageHeader ^2 #Header :5\n"
            "    @ Controls/PageHeader.xaml ^2  (UserControl, dc:HeaderVM)\n"
            "      Image ^3 :11\n"
        )
        g = build(text)
        header = node(g, "component.page-header")
        self.assertEqual(header["properties"]["uno"], {"type": "UserControl", "xName": "Header"})
        self.assertEqual(header["properties"]["dataContextType"], "HeaderVM")
        self.assertEqual(header["evidence"]["locator"], {"ref": "2", "file": "Controls/PageHeader.xaml", "line": 5})
        image = next(n for n in g["nodes"] if n["properties"]["uno"]["type"] == "Image")
        parent_of = {e["to"]: e["from"] for e in g["edges"] if e["relation"] == "contains"}
        self.assertEqual(parent_of[image["id"]], "component.page-header")
        self.assertEqual(image["evidence"]["locator"]["file"], "Controls/PageHeader.xaml")
        self.assertEqual(sum(1 for n in g["nodes"] if n["evidence"]["locator"]["ref"] == "2"), 1)

    def test_empty_input_has_no_roots(self):
        self.assertEqual(s2g.parse_snapshot("\n\n"), [])
        with self.assertRaises(ValueError):
            s2g.build_graph([], None, None, False, None)

    def test_binding_variants(self):
        self.assertEqual(s2g.parse_binding("IsEnabled", "CanSave"), {"property": "IsEnabled", "path": "CanSave"})
        self.assertEqual(s2g.parse_binding("Text", "Name,1way|conv"),
                         {"property": "Text", "path": "Name", "mode": "1way", "converter": True})


class GraphIsClean(unittest.TestCase):
    def test_generated_graph_validates_and_lints_strict(self):
        g = build()
        self.assertEqual(validate_graph(write_tmp(g), SCHEMA), [])
        r = lint_graph.lint(g)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.warnings, [])


class DiffAgainstDesign(unittest.TestCase):
    def setUp(self):
        with EXAMPLE.open(encoding="utf-8") as f:
            self.design = json.load(f)

    def test_named_controls_match_and_missing_style_key_is_drift(self):
        d = diff_graph.diff(self.design, build(), only_mapped=True)
        missing = {m["id"] for m in d["missing"]}
        self.assertNotIn("control.profile.username", missing)
        self.assertNotIn("control.profile.save", missing)
        changed = {(c["id"], c["key"]): c for c in d["changed"]}
        self.assertIn(("control.profile.save", "styleKey"), changed)
        self.assertEqual(changed[("control.profile.save", "styleKey")]["actual"], None)

    def test_snapshot_cannot_supply_class_tokens_or_states(self):
        d = diff_graph.diff(self.design, build(), only_mapped=True)
        changed = {(c["id"], c["key"]) for c in d["changed"]}
        self.assertIn(("screen.settings", "class"), changed)
        self.assertIn(("component.page-header", "class"), changed)
        missing = {m["id"] for m in d["missing"]}
        self.assertTrue({"token.color.surface1", "token.radius.12", "state.profile.saved"} <= missing)

    def test_design_hint_adopts_node_type_for_confirmed_xnames(self):
        hinted = build(design=self.design)
        d = diff_graph.diff(self.design, hinted, only_mapped=True)
        self.assertNotIn("component.settings-card.profile", {m["id"] for m in d["missing"]})
        # The hint adopts the type only: the id stays runtime-derived and uno.* carries only what the snapshot exposes.
        card = by_xname(hinted, "ProfileSection")
        self.assertEqual(card["type"], "component")
        self.assertEqual(card["id"], "component.profile-section")
        self.assertEqual(card["properties"]["uno"], {"type": "Border", "xName": "ProfileSection"})

    def test_design_hinted_graph_validates_and_lints_strict(self):
        g = build(design=self.design)
        self.assertEqual(validate_graph(write_tmp(g), SCHEMA), [])
        r = lint_graph.lint(g)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.warnings, [])


class Cli(unittest.TestCase):
    def test_cli_writes_graph_and_diff_exits_one_on_drift(self):
        out = Path(tempfile.mkdtemp()) / "runtime.graph.json"
        p = subprocess.run([sys.executable, str(SCRIPTS / "snapshot_to_graph.py"), str(FIXTURE), "-o", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(out.exists())
        for script in ("validate_graph.py", "lint_graph.py"):
            q = subprocess.run([sys.executable, str(SCRIPTS / script), str(out)], capture_output=True, text=True)
            self.assertEqual(q.returncode, 0, q.stdout + q.stderr)
        r = subprocess.run([sys.executable, str(SCRIPTS / "diff_graph.py"), str(EXAMPLE), str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("uno.styleKey: 'OrbitalPrimaryButtonSm' -> None", r.stdout)

    def test_cli_rejects_empty_input(self):
        p = subprocess.run([sys.executable, str(SCRIPTS / "snapshot_to_graph.py"), "-"],
                           input="", capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
