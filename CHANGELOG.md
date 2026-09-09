# Changelog

Versions before 0.6.0 were tracked in the Design Graph Kit's `CHANGELOG.md`
in [mtmattei/Uno-Builds](https://github.com/mtmattei/Uno-Builds/tree/main/design-graph-kit).
From 0.6.0 the plugin is versioned here.

## 0.6.0

Plugin and skill renamed `design-graph` -> `uno-design-graph` to follow the
`uno-<category>-<topic>` grammar used by the Uno Platform Studio skill catalog.

### Schema 0.2.0

- `schemaVersion` accepts `0.1`, `0.1.0`, and `0.2.0`. Graphs declaring
  `0.2.0` get a typed `properties.uno` mapping layer per node type; unknown
  keys in that layer are now schema errors instead of silent score zeros.
- `uno.namespace` added for non-WinUI control types (Toolkit, custom). The
  xmlns prefix never belongs in `uno.type`.
- `metadata.kind` (`screen` | `design-system`) added for the design-system
  graph profile.

### Scripts

- `lint_graph.py` (new): enforces the binding rules that previously lived
  only in prose. ID grammar, relation domains, per-instance token edges,
  style-level state names, unresolved references, confidence thresholds,
  behavior-edge evidence, unconsumed tokens, unattached states.
- `snapshot_to_graph.py` (new): builds a runtime graph from the text of
  `uno_app_visualtree_snapshot` (Uno.UI.App.Mcp 1.3.x line grammar). Copies
  `uno.type` and `uno.xName`, keeps source locators, flags, bindings, and
  bounds; `--design` adopts the design graph's node types for confirmed
  `x:Name`s so the diff matches semantic nodes. Ships with a reconstructed
  fixture, not a live capture.
- `diff_graph.py` (new): reports Uno-layer drift (`type`, `xName`,
  `styleKey`, `resourceKey`) between two graphs. This is the executable form
  of the round-trip contract.
- `score_graph.py` 0.4.0: the `unresolved` dimension matches on overlapping
  `relatedIds` instead of exact tuples; `--fail-on-hallucination` returns a
  non-zero exit code when unsupported behavior edges exist.
- Tests under `scripts/tests/` run in CI.

### Skill

- Script paths use `${CLAUDE_SKILL_DIR}` so they resolve from any project.
- New Mode 3: verify the running app against a graph via the Uno App MCP
  visual tree snapshot and `diff_graph.py`. See `references/runtime-source.md`.
- `prompts/design-understanding.md` removed; `references/method.md` is the
  single generation procedure.
- Dangling references to kit-only docs removed.
- Version headers aligned across method, ontology, scorer, schema, and manifests.

### Repository

- `docs/hotdesign-integration-findings.md`: read-only study of
  `unoplatform/uno.hotdesign` answering what the Elements tree carries, how
  panels are hosted, what the snapshot format is, and how selection syncs,
  with a sketch of the smallest MCP selection bridge.

- `examples/orbital-settings.graph.json`: the README excerpt as a complete,
  validated graph.
- GitHub Actions workflow runs validate, lint, score, diff, and the tests.
