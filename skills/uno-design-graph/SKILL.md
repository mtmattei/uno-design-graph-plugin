---
name: uno-design-graph
description: Generate a Design Graph (semantic JSON IR of a UI screen — structure, components, states, tokens, Uno mapping) from an Uno/WinUI app's source or a screenshot; implement a screen FROM an existing Design Graph; or verify the running app against one via the Uno App MCP. Use when the user asks to "generate a design graph", "map this screen", "extract the design", analyze a screen's design semantics, build a screen from a *.graph.json, or check an implementation for design drift. Also validates, lints, scores, and diffs graphs.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Uno Design Graph

A Design Graph is a semantic, machine-checkable intermediate representation
between a UI design, its Uno Platform implementation, and the running app.
It records what a screen *means* — structure, reusable components, states,
tokens, and the relationships between them — not how it is drawn.

Everything this skill needs is bundled alongside this file at
`${CLAUDE_SKILL_DIR}`. Every command below uses that path so it works from
any project directory.

## Mode 1 — Generate a graph

1. Read and follow, in order:
   - `${CLAUDE_SKILL_DIR}/references/method.md` — the 10-pass procedure and
     every binding rule: ID grammar, naming vocabulary, state altitude,
     canonical internals, token scoping, `uses-token` attachment, graph
     kinds, and the Uno mapping layer
   - `${CLAUDE_SKILL_DIR}/schema/design-graph.schema.json`
   - `${CLAUDE_SKILL_DIR}/references/ontology.md`
   - `${CLAUDE_SKILL_DIR}/references/inference-rules.md`
   - `${CLAUDE_SKILL_DIR}/references/token-rules.md`
   - `${CLAUDE_SKILL_DIR}/references/uno-mapping.md`
2. Gather the input:
   - **Source-backed** (XAML + code-behind/ViewModel/model + style
     dictionaries): expand every custom-control reference. A referenced
     `UserControl` is a declared component whose internals belong in the
     graph — missing one is the single most common answer-key defect.
   - **Design-only** (screenshot or mock): behavior stays `unresolved` and
     the Uno mapping is a proposed realization marked `inferred`.
   - **Runtime** (the running app via the Uno App MCP): follow
     `${CLAUDE_SKILL_DIR}/references/runtime-source.md`.
3. If the Uno Platform docs MCP server is available (`mcp__uno__*`), use it
   to resolve control identity and Themes/resource idioms for
   `properties.uno`. Use it for nothing in the semantic layer.
4. Write `<name>.graph.json` with `"schemaVersion": "0.2.0"` and run both
   checks until both pass:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/validate_graph.py <file>
   python3 ${CLAUDE_SKILL_DIR}/scripts/lint_graph.py <file>
   ```
   Validate checks the schema and integrity. Lint checks the binding rules.
   Read every lint warning; fix it or leave it knowingly.
5. Never invent behavior. Bindings, commands, and handlers are declared
   evidence; visual plausibility is not. Prefer `unresolved` over a low
   confidence guess.

## Mode 2 — Implement from a graph

Follow `${CLAUDE_SKILL_DIR}/prompts/design-implement.md`. The graph is the
semantic source of truth: hierarchy, canonical components plus
`instance-of`, `has-state` and `triggers`, and `uses-token`. Honor the
`properties.uno` mapping layer — adopt its resource keys, `x:Name`s, and
control types verbatim so the result stays traceable to the source design
system.

Two rules carry most of the measured value:

- **Do not implement behavior the graph leaves `unresolved`.** In the kit's
  A/B experiment the arm without a graph invented a plausible URL for a
  documentation button and got it wrong; the graph arms left genuinely
  unknown actions unwired and matched the real app exactly on the known one.
- **Copy identifiers, don't coin them.** Reusing the graph's `x:Name`s and
  resource keys is what makes a later diff against the source design system
  exact rather than approximate.

Finish with Mode 3.

## Mode 3 — Verify the running app against a graph

Build a runtime graph per
`${CLAUDE_SKILL_DIR}/references/runtime-source.md` (drive the app with the
App MCP, snapshot the visual tree, record only what you observed), then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/diff_graph.py <design>.graph.json <runtime>.graph.json
```

Any `missing` or `changed` identity (`uno.type`, `uno.xName`,
`uno.styleKey`, `uno.resourceKey`, `uno.namespace`) is a round-trip defect.
Fix the implementation, not the design graph, unless the design graph was
wrong and you can cite the source that proves it.

## Scoring against a gold graph

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/score_graph.py <gold> <generated> [--json] [--fail-on-hallucination]
```

Six dimensions, including an id-drift-tolerant `node_concept` measure and a
`uno_mapping` measure that scores exact recovery of (node type, uno key, uno
value) triples — the copy-don't-coin contract, independent of id spelling.
`unresolved` matches on overlapping `relatedIds`, so a reworded question
about the same nodes still counts.

Scoring needs a hand-authored gold graph. Same-session gold and generated
graphs score near-perfectly and prove nothing; blind runs in fresh contexts
are the only meaningful stability evidence.

## Requirements

`validate_graph.py` needs `jsonschema`; the other scripts are stdlib only.

```bash
python3 -m pip install -r ${CLAUDE_SKILL_DIR}/scripts/requirements.txt
```

## Provenance

Extracted from the Design Graph Kit (`design-graph-kit/` in
github.com/mtmattei/Uno-Builds), where the full experiment record lives:
eval cases with gold graphs, blind replication fleets, A/B implementation
arms, and the results that produced the rules in `references/`.
