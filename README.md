# Design Graph — Claude Code plugin

A **Design Graph** is a semantic, machine-checkable intermediate representation
between a UI design and its Uno Platform implementation. It records what a
screen means — structure, reusable components, states, tokens, and the
relationships between them — rather than how it is drawn.

This plugin packages the graph method as an installable Claude Code skill:
generate a graph from an app's source, a Figma export, or a screenshot;
implement a screen from an existing graph; validate and score graphs.

## Install

```
/plugin marketplace add mtmattei/uno-design-graph-plugin
/plugin install design-graph
```

The repo doubles as its own marketplace, so the two commands above are all it
takes. Once installed the skill loads in any project — the schema, ontology,
rules, prompts, and scripts travel with it.

Interim alternative with no packaging at all: copy `skills/design-graph/` into
`~/.claude/skills/` for personal use on one machine.

## What it does

| Mode | Trigger | Output |
|---|---|---|
| Generate | "generate a design graph of X", "map this screen" | validated `<name>.graph.json` |
| Implement | "build this screen from `x.graph.json`" | XAML + code-behind traceable to the graph |
| Score | comparing against a hand-authored gold graph | six-dimension F1 report |

Validation needs one dependency:

```bash
python3 -m pip install -r skills/design-graph/scripts/requirements.txt
```

## What a graph looks like

An abridged excerpt from a real one: the
[eval-05 gold graph](https://github.com/mtmattei/Uno-Builds/blob/main/design-graph-kit/evals/05-orbital-settings/gold.graph.json)
(65 nodes, 96 edges), authored from the Orbital app's `SettingsPage.xaml`,
its code-behind, and the Orbital style dictionaries. Every identifier below —
control types, `x:Name`s, style keys — is copied verbatim from that source.

```jsonc
{
  "schemaVersion": "0.1",
  "graphId": "orbital-settings",
  "name": "Orbital Settings",
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
      "properties": { "uno": { "type": "Grid" } }
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
    // ... 59 more nodes: regions, cards, fields, dialog, entrance states, tokens
  ],
  "edges": [
    { "from": "screen.settings", "relation": "contains", "to": "region.settings-content", /* ... */ },
    { "from": "component.settings-card.profile", "relation": "contains", "to": "control.profile.save", /* ... */ },
    { "from": "component.info-row.platform", "relation": "instance-of", "to": "component.info-row", /* ... */ },
    { "from": "component.settings-card", "relation": "uses-token", "to": "token.radius.12", /* ... */ },
    { "from": "control.profile.save", "relation": "triggers", "to": "state.profile.saved",
      "evidence": { "kind": "declared", "confidence": 1.0,
        "source": { "type": "csharp", "path": "Orbital/Orbital/Presentation/SettingsPage.xaml.cs" },
        "rationale": "Save handler swaps content to 'Saved!' after persisting the name." } },
    { "from": "control.profile.save", "relation": "has-state", "to": "state.profile.saved", /* ... */ }
    // ... 90 more edges
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
  in the Orbital source, character for character. A design-only input would
  carry the same layer marked `inferred` instead.
- **Behavior edges require code.** The `triggers` / `has-state` pair on the
  Save button cites the code-behind line that swaps its content to "Saved!".
  Visual plausibility alone never produces a behavior edge.
- **Repetition folds into components.** Four identical label/value grids
  become one canonical `component.info-row` plus thin instances, connected by
  `instance-of`.
- **Unknowns are recorded, not invented.** The header search raises an event
  whose handler is outside the source set, so the graph says exactly that in
  `unresolved` instead of guessing a destination.

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

Versions stay in lockstep with the kit's `CHANGELOG.md`.
