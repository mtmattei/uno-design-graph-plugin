---
name: design-graph
description: Generate a Design Graph (semantic JSON IR of a UI screen — structure, components, states, tokens, Uno mapping) from an Uno/WinUI app's source, a Figma export, or a screenshot; or implement a screen FROM an existing Design Graph. Use when the user asks to "generate a design graph", "map this screen", "extract the design", analyze a screen's design semantics, or build a screen from a *.graph.json. Also validates and scores graphs.
---

# Design Graph

A Design Graph is a semantic, machine-checkable intermediate representation
between a UI design and its Uno Platform implementation. It records what a
screen *means* — structure, reusable components, states, tokens, and the
relationships between them — not how it is drawn.

Everything this skill needs is bundled alongside this file. Paths below are
relative to this skill's own directory, so the skill works in any project.

## Mode 1 — Generate a graph

1. Read and follow, in order:
   - `references/method.md` — the 10-pass procedure and every binding rule:
     ID grammar, naming vocabulary, state altitude, canonical internals,
     token scoping, `uses-token` attachment, and the Uno mapping layer
   - `schema/design-graph.schema.json`
   - `references/ontology.md`
   - `references/inference-rules.md`
   - `references/token-rules.md`
   - `references/uno-mapping.md`
2. Gather the input:
   - **Source-backed** (XAML + code-behind/ViewModel/model + style
     dictionaries): expand every custom-control reference. A referenced
     `UserControl` is a declared component whose internals belong in the
     graph — missing one is the single most common answer-key defect.
   - **Design-only** (image/Figma/mock): behavior stays `unresolved` and the
     Uno mapping is a proposed realization marked `inferred`.
3. If an Uno Platform docs MCP server is available (`mcp__uno__*`), use it to
   resolve control identity and Themes/resource idioms for `properties.uno`.
4. Write `<name>.graph.json` and validate until it passes:
   ```bash
   python3 scripts/validate_graph.py <file>
   ```
5. Never invent behavior. Bindings, commands, and handlers are declared
   evidence; visual plausibility is not. Prefer `unresolved` over a low
   confidence guess.

## Mode 2 — Implement from a graph

Follow `prompts/design-implement.md`. The graph is the semantic source of
truth: hierarchy, canonical components plus `instance-of`, `has-state` and
`triggers`, and `uses-token`. Honor the `properties.uno` mapping layer —
adopt its resource keys, `x:Name`s, and control types verbatim so the result
stays traceable to the source design system.

Two rules carry most of the measured value:

- **Do not implement behavior the graph leaves `unresolved`.** In the kit's
  A/B experiment the arm without a graph invented a plausible URL for a
  documentation button and got it wrong; the graph arms left genuinely
  unknown actions unwired and matched the real app exactly on the known one.
- **Copy identifiers, don't coin them.** Reusing the graph's `x:Name`s and
  resource keys is what makes a later diff against the source design system
  exact rather than approximate.

## Scoring against a gold graph

```bash
python3 scripts/score_graph.py <gold> <generated> [--json]
```

Six dimensions, including an id-drift-tolerant `node_concept` measure and a
`uno_mapping` measure that scores exact recovery of (node type, uno key, uno
value) triples — the copy-don't-coin contract, independent of id spelling.

Scoring needs a hand-authored gold graph. Same-session gold and generated
graphs score near-perfectly and prove nothing; blind runs in fresh contexts
are the only meaningful stability evidence.

## Requirements

`scripts/validate_graph.py` needs `jsonschema`:

```bash
python3 -m pip install -r scripts/requirements.txt
```

## Provenance

Extracted from the Design Graph Kit (`design-graph-kit/` in
github.com/mtmattei/Uno-Builds), where the full experiment record lives:
eval cases with gold graphs, blind replication fleets, A/B implementation
arms, and the results that produced the rules in `references/`.
