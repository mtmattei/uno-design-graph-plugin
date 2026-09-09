# Runtime Source: the running app as evidence

The schema's `source.type` has always allowed `runtime`. The Uno App MCP
makes it practical: `uno_app_visualtree_snapshot` returns the live visual
tree, `uno_app_get_screenshot` the rendered surface, and (Pro)
`uno_app_get_element_datacontext` the DataContext of an element. A graph
built from those is "what actually got built", and diffing it against the
design graph is the executable form of the round-trip contract in
`uno-mapping.md`, rule 4.

## When to use it

- **Mode 3, verify.** After implementing from a graph, before handing back.
- **After a Hot Design session.** Hot Design edits XAML on the running app;
  a diff shows whether any resource key, style key, or `x:Name` drifted.
- **Parity of an existing app.** Source-backed graph vs runtime graph shows
  what the source declares but never renders, and what renders without a
  declared identity.

## Building a runtime graph

1. Drive the app to the screen and state you are verifying
   (`uno_app_pointer_click`, `uno_app_type_text`,
   `uno_app_element_peer_default_action`). One graph per presentation
   condition; name the file `<name>.runtime.<state>.graph.json`.
2. Take `uno_app_visualtree_snapshot` and `uno_app_get_screenshot`.
3. Build the graph mechanically:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/snapshot_to_graph.py snapshot.txt \
       --design <design>.graph.json -o <name>.runtime.<state>.graph.json
   ```

   The parser copies `uno.type` and `uno.xName` from the snapshot, records
   every node as `observed` / `runtime` with a locator (`ref`, `file`,
   `line`, `flags`), drops `lib:` template internals unless `--include-lib`,
   and keeps `dc:`, bindings, bounds, and flags as properties. `--design`
   adopts the design graph's node *type* for `x:Name`s the runtime confirms
   so the diff matches semantic nodes; it never copies ids or `uno.*` values.

   What the snapshot cannot supply, and the diff will always report:
   `uno.styleKey`, `uno.resourceKey`, `uno.class`, `uno.namespace`, states,
   and tokens. Those come from Hot Design's own tree or the source; see
   `docs/hotdesign-integration-findings.md` in the plugin repo.

   Hand-authoring is still allowed when the snapshot is unavailable. Then:
   - `evidence.kind` is `observed` and `evidence.source.type` is `runtime`.
   - Behavior edges (`triggers`, `navigates-to`) only for transitions you
     drove and observed in this session; record the action in the rationale.
   - States only for conditions you drove the app into.
   - Tokens only when the snapshot exposes the key, or the value matches a
     design-graph token exactly (reuse that id and cite the match).

4. Validate and lint as usual. Then diff:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/diff_graph.py <design>.graph.json <name>.runtime.<state>.graph.json
   ```

## Reading the diff

- `missing`: a design identity that did not render. Usually a dropped
  `x:Name` or a control replaced by a different type.
- `changed`: same identity, different `type`, `styleKey`, `resourceKey`,
  or `namespace`. This is the parity defect the contract exists to catch.
- `extra`: rendered identities the design graph lacks. Not a failure by
  default (`--fail-on-extra` makes it one); often template internals the
  snapshot exposes, sometimes a control the implementation added.

The snapshot text format is owned by the Uno tooling (`Uno.UI.App.Mcp`).
The parser targets the 1.3.x line grammar documented in its docstring; a
format change shows up as parse failures, not silent drift.
