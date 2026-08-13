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
