# Uno Design Graph — Claude Code plugin

A **Design Graph** is a semantic, machine-checkable intermediate representation
between a UI design, its Uno Platform implementation, and the running app. It
records what a screen means — structure, reusable components, states, tokens,
and the relationships between them — rather than how it is drawn.

This plugin packages the graph method as an installable Claude Code skill:
generate a graph from an app's source or a screenshot; implement a screen from
an existing graph; verify the running app against one through the Uno App MCP;
validate, lint, score, and diff graphs.

## Install

```
/plugin marketplace add mtmattei/uno-design-graph-plugin
/plugin install uno-design-graph@uno-design-graph
```

The repo doubles as its own marketplace, so the two commands above are all it
takes. Once installed the skill loads in any project — the schema, ontology,
rules, prompts, and scripts travel with it. It sits alongside the
`uno-platform-studio` plugin and follows the same `uno-<category>-<topic>`
skill naming.

Interim alternative with no packaging at all: copy `skills/uno-design-graph/`
into `~/.claude/skills/` for personal use on one machine.

## What it does

| Mode | Trigger | Output |
|---|---|---|
| Generate | "generate a design graph of X", "map this screen" | validated and linted `<name>.graph.json` |
| Implement | "build this screen from `x.graph.json`" | XAML + code-behind traceable to the graph |
| Verify | "check the running app against `x.graph.json`" | Uno-layer drift report from the App MCP visual tree |
| Score | comparing against a hand-authored gold graph | six-dimension F1 report |

## Scripts

All under `skills/uno-design-graph/scripts/`. Only `validate_graph.py` needs a
dependency:

```bash
python3 -m pip install -r skills/uno-design-graph/scripts/requirements.txt
```

| Script | Checks | Exit 1 when |
|---|---|---|
| `validate_graph.py <graph>` | JSON Schema, unique ids, resolvable edges, no duplicate edges, rationale on inferences | any error |
| `lint_graph.py <graph> [--strict]` | the binding rules: ID grammar, relation domains, per-instance token edges, style-level states, unresolved refs, confidence thresholds, behavior-edge evidence, unconsumed tokens, unattached states | any error (`--strict`: any warning) |
| `score_graph.py <gold> <generated> [--json] [--fail-on-hallucination]` | six F1 dimensions plus an unsupported-behavior proxy | `--fail-on-hallucination` and unsupported behavior edges exist |
| `diff_graph.py <design> <actual> [--fail-on-extra]` | drift in `uno.type`, `xName`, `styleKey`, `resourceKey`, `namespace` between two graphs | any missing or changed identity |

Run the whole suite:

```bash
python3 -m unittest discover -s skills/uno-design-graph/scripts/tests
```

## What a graph looks like

[`examples/orbital-settings.graph.json`](examples/orbital-settings.graph.json)
is a complete graph that passes every script. It is abridged from the
[eval-05 gold graph](https://github.com/mtmattei/Uno-Builds/blob/main/design-graph-kit/evals/05-orbital-settings/gold.graph.json)
(65 nodes, 96 edges), authored from the Orbital app's `SettingsPage.xaml`,
its code-behind, and the Orbital style dictionaries. Every identifier —
control types, `x:Name`s, style keys — is copied verbatim from that source.
An excerpt:

```jsonc
{
  "schemaVersion": "0.2.0",
  "graphId": "orbital-settings",
  "name": "Orbital Settings",
  "metadata": { "kind": "screen" },
  "nodes": [
    {
      "id": "screen.settings",
      "type": "screen",
      "name": "Settings",
      "evidence": { "kind": "observed", "confidence": 1.0,
        "source": { "type": "xaml", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml" } },
      "properties": { "uno": { "type": "Page", "class": "Orbital.Presentation.SettingsPage" } }
    },
    {
      "id": "control.profile.save",
      "type": "control",
      "name": "Save",
      "role": "button",
      "semanticRole": "primaryAction",
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "xaml", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml" },
        "rationale": "x:Name=SaveUsernameButton, OrbitalPrimaryButtonSm (only high-emphasis action)." },
      "properties": { "uno": { "type": "Button", "styleKey": "OrbitalPrimaryButtonSm", "xName": "SaveUsernameButton" } }
    },
    {
      "id": "component.info-row",           // canonical: four label/value rows fold into one concept
      "type": "component",
      "name": "Info row (label/value)",
      "role": "keyValueRow",
      "evidence": { "kind": "derived", "confidence": 1.0,
        "source": { "type": "xaml", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml" },
        "rationale": "Four label/value grids with identical structure inside ABOUT." },
      "properties": { "parts": ["label", "value"], "uno": { "type": "Grid" } }
    },
    {
      "id": "component.info-row.platform",  // instance: carries only what differs
      "type": "component",
      "name": "Platform",
      "properties": { "value": "{Binding PlatformInfo}" },
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "xaml", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml" } }
    },
    {
      "id": "state.profile.saved",          // a presentation condition, owned by the button that changes
      "type": "state",
      "name": "Saved",
      "semanticRole": "confirmation",
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "csharp", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml.cs" },
        "rationale": "Save sets button content to 'Saved!' for 1.5s after SettingsService.SaveUsername." },
      "properties": { "uno": { "mechanism": "code-behind" } }
    },
    {
      "id": "token.radius.12",
      "type": "token",
      "name": "12 radius",
      "category": "radius",
      "value": 12,
      "properties": { "unit": "px", "uno": { "styleKey": "OrbitalCardStyle", "property": "CornerRadius" } },
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "design-system", "label": "Orbital Styles/*.xaml" },
        "rationale": "OrbitalCardStyle CornerRadius." }
    }
    // ... see the example file for the header, cards, fields, entrance state, and second token
  ],
  "edges": [
    { "from": "screen.settings", "relation": "contains", "to": "region.settings.content", /* ... */ },
    { "from": "component.settings-card.profile", "relation": "contains", "to": "control.profile.save", /* ... */ },
    { "from": "component.info-row.platform", "relation": "instance-of", "to": "component.info-row", /* ... */ },
    { "from": "component.settings-card", "relation": "uses-token", "to": "token.radius.12", /* ... */ },
    { "from": "control.profile.save", "relation": "triggers", "to": "state.profile.saved",
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "csharp", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml.cs" },
        "rationale": "Save handler swaps content to 'Saved!' after persisting the name." } },
    { "from": "control.profile.save", "relation": "has-state", "to": "state.profile.saved", /* ... */ }
  ],
  "unresolved": [
    {
      "id": "unresolved.header.search-target",
      "question": "What UI does the header search / command palette open?",
      "relatedIds": ["control.header.search"],
      "possibleValues": ["global command palette", "search overlay", "unknown"],
      "reason": "PageHeader raises a static SearchRequested event; the handler and resulting UI are outside the supplied source."
    }
  ]
}
```

What to notice:

- **Every claim carries evidence.** `observed` / `declared` / `derived` /
  `inferred`, with a source path and, for anything non-obvious, a rationale.
- **The `properties.uno` mapping layer is copied, never coined.** `Button`,
  `OrbitalPrimaryButtonSm`, `SaveUsernameButton`, `OrbitalCardStyle` all exist
  in the Orbital source, character for character. Since schema 0.2.0 the
  layer is typed: a misspelled key fails validation instead of silently
  scoring zero. A design-only input would carry the same layer marked
  `inferred` instead.
- **Behavior edges require code.** The `triggers` / `has-state` pair on the
  Save button cites the code-behind line that swaps its content to "Saved!".
  Visual plausibility alone never produces a behavior edge, and the linter
  rejects an inferred one.
- **Repetition folds into components.** Four identical label/value grids
  become one canonical `component.info-row` plus thin instances, connected by
  `instance-of`. The canonical declares its `parts` once; instances carry only
  what differs.
- **Unknowns are recorded, not invented.** The header search raises an event
  whose handler is outside the source set, so the graph says exactly that in
  `unresolved` instead of guessing a destination.

## Where it sits in the Uno stack

Hot Design edits XAML on the running app. The Studio Agent reads the live
visual tree and works inside your design system. The App MCP exposes the
visual tree, screenshots, and DataContext to any agent. None of them carries
a durable, checkable record of what a screen was supposed to mean. The graph
is that record:

- **Memory for the agent.** A `design-system` graph is the portable form of
  "know your design system"; token nodes keep the exact Uno.Themes keys.
- **Contract for image-driven work.** Screenshot → graph → implementation,
  with evidence and an `unresolved` list in the middle.
- **Parity check.** A graph built from the App MCP visual tree, diffed
  against the design graph, is the round-trip contract made executable. See
  `skills/uno-design-graph/references/runtime-source.md`.

## Why the rules are shaped the way they are

Every binding rule in `references/` came out of a measured failure, not taste.
A few that matter:

- **Never implement behavior the graph leaves `unresolved`.** In the source
  experiment, the implementation arm working from a visual brief alone invented
  a plausible URL for a documentation button — and it was wrong. The arms
  working from a graph left genuinely unknown actions unwired and matched the
  real app exactly on the known ones.
- **Copy identifiers, don't coin them.** Carrying the source's `x:Name`s and
  resource keys verbatim is what makes a later diff against the real design
  system exact instead of approximate.
- **Expand every declared component reference.** A referenced `UserControl` is
  a component whose internals belong in the graph; missing one was the single
  most common answer-key defect.
- **Prefer omission to invention.** A missing field costs recall; a fabricated
  one costs trust in the whole graph.

## Provenance

Extracted from the Design Graph Kit in
[mtmattei/Uno-Builds](https://github.com/mtmattei/Uno-Builds/tree/main/design-graph-kit),
which holds the full experiment record: eval cases with hand-authored gold
graphs, blind replication fleets across three architectures, A/B implementation
arms, and the results that produced these rules.

From 0.6.0 the plugin is versioned in [`CHANGELOG.md`](CHANGELOG.md).
