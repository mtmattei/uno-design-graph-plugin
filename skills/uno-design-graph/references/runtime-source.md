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
3. Produce a graph with the same ontology and ID grammar as a source-backed
   graph. Differences from Mode 1:
   - `evidence.kind` is `observed` and `evidence.source.type` is `runtime`.
     Put the snapshot's element path or index in `evidence.locator`.
   - `uno.type` is the runtime type name from the snapshot, `uno.xName` its
     `Name`, and `uno.styleKey` only when the snapshot exposes the style
     resource key. Copy, don't coin.
   - Behavior edges (`triggers`, `navigates-to`) are allowed **only** for
     transitions you drove and observed in this session. Record the driving
     action in the edge's `evidence.rationale`.
   - States come from what you drove the app into. A state you did not
     observe does not exist in a runtime graph.
   - Tokens: a runtime tree exposes resolved values, not keys. Create a
     token node only when the snapshot exposes the key, or when the value
     matches a token in the design graph exactly (then reuse that token id
     and cite the match in the rationale).
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

The snapshot text format is owned by the Uno tooling. When it stabilizes, a
parser can replace step 3; until then the mapping above is the contract.
