# Skill: Generate Design Graph

Version: 0.4 (0.2 added a binding ID grammar, state-altitude rules, and token
scoping; 0.3 added canonical-internals, token-edge attachment, and
variant-folding rules; 0.4 makes the graph **Uno-first** — every node may
carry a `properties.uno` mapping layer per `references/uno-mapping.md`. See
CHANGELOG.)

## Target framework

The Design Graph targets **Uno Platform** (WinUI XAML, Uno Toolkit,
Uno Themes). Alongside the semantic fields, populate the `properties.uno`
mapping layer following `references/uno-mapping.md`: exact control types,
`x:Name`s, style keys, and resource keys when the source declares them
(copied verbatim, never re-coined), or a proposed realization marked
`inferred` when the input is design-only. When an Uno Platform docs MCP
server is available, use it to resolve control identity and Toolkit/Themes
idioms for this layer. Omit a `uno` field rather than invent one.

## Purpose

Analyze a UI design, runtime UI, design document, or source-backed application and produce a **Design Graph**: a semantic, machine-readable representation of the design's structure, reusable components, controls, states, design tokens, and relationships.

The graph is an intermediate representation. Do not generate implementation code while executing this skill unless the caller separately asks for implementation after the graph is complete.

## Inputs

Use any available combination of:

- screenshot or image;
- Figma/design-document structure;
- existing XAML;
- existing C#;
- runtime UI inspection;
- HTML/DOM;
- design-system definitions;
- design tokens;
- explicit user description.

Input quality varies. Represent partial knowledge honestly.

## Required references

Before generating a graph, follow:

1. `schema/design-graph.schema.json`
2. `references/ontology.md`
3. `references/inference-rules.md`
4. `references/token-rules.md`
5. `references/uno-mapping.md`

## Output

Produce one JSON document conforming to:

`schema/design-graph.schema.json`

Default filename:

`design.graph.json`

Do not wrap the JSON in explanatory prose if the caller asks for a file or machine-readable result.

## Procedure

### Pass 1: Inventory observable facts

Identify only what is directly supported by the source:

- screens or major views;
- visible regions;
- visible controls;
- visible text/content;
- assets;
- geometry if available;
- colors;
- typography;
- spacing;
- borders/radii;
- source-backed component names;
- source-backed states.

Mark these as `observed`, `declared`, or `derived` as appropriate.

Do not infer behavior during this pass.

### Pass 2: Establish structural hierarchy

Build `contains` relationships from coarse to fine:

`screen -> region -> component -> control/content/asset`

Prefer meaningful semantic containers over reproducing every drawing-layer wrapper.

Do not recreate a Figma layer tree verbatim when intermediate frames/groups have no semantic value.

### Pass 3: Detect repetition

Look for recurring structures with comparable:

- child roles;
- visual treatment;
- spacing;
- typography;
- purpose;
- source identity.

When multiple items are clearly instances of one reusable concept:

1. create a canonical `component` node;
2. create instance nodes only when the instances need distinct identity;
3. connect instances with `instance-of`.

Do not collapse merely similar objects when their semantics differ.

Canonical internals (binding): a canonical component's internal parts (its
label, value, icon slots) are described once, as `properties` on the
canonical node (e.g. `"parts": ["label", "value"]`) — never as child nodes of
the canonical or of each instance. Instance nodes carry only what differs per
instance (name, bound value), also as `properties`. Create a child node under
an instance only when that instance genuinely overrides the canonical
structure. (Blind evals showed generators re-modeling template internals as
nodes, one level below the intended altitude.)

### Pass 4: Identify states and variants

When multiple presentations represent the same conceptual UI under different conditions:

- create one canonical screen/component;
- create `state` nodes;
- connect using `has-state`.

State altitude (binding): model only screen/component **presentation
conditions** (loading, empty, populated, error, saved, entering, disabled at
the component level). Do **not** create `state` nodes for style-level
interaction visuals — PointerOver, Pressed, Focused, or a control template's
Disabled visual belong to the design system's style definitions, not to a
screen graph.

Attach `has-state` to the **smallest node whose presentation actually
changes**: a button whose label flips to "Saved!" owns that state; a section
that swaps to a skeleton owns its loading state; only whole-screen conditions
attach to the screen.

Examples:

- loading;
- empty;
- populated;
- error;
- disabled;
- selected.

Use `variant-of` when two components are stable variants of the same component concept rather than transient states.

### Pass 5: Normalize candidate design tokens

Use `references/token-rules.md`.

Scope (binding): create tokens only for values the modeled surface actually
consumes (directly or via a style it uses). Never enumerate an entire style
dictionary or palette — a full design-system inventory belongs in a separate
design-system graph, not a screen graph.

Variant folding (binding): interaction-only variants of a base value —
hover/pressed shades, alpha steps of an accent, focus tints — are style
internals; tokenize the **base** value only. If a surface visibly uses two
distinct emphasis levels (e.g. label vs value text), those are two tokens;
a hover lightening of a button is not.

Token-edge attachment (binding): `uses-token` edges attach to the canonical
component (or the screen for page-level values) — **once per token per
concept**, not per instance and not per internal part. Attach a token edge to
an instance only when that instance overrides the canonical value. (Blind
evals showed 6× edge inflation from per-instance wiring.)

Create `token` nodes for recurring or explicitly declared values such as:

- color;
- typography;
- spacing;
- radius;
- border;
- elevation;
- size.

Prefer semantic token names when source evidence supports them.

When semantic naming is not supported, use stable neutral names such as:

- `token.color.1`
- `token.spacing.16`
- `token.radius.8`

Connect consumers using `uses-token`.

### Pass 6: Infer semantics conservatively

Infer concepts only when useful and reasonably supported.

Every inference must:

- use `evidence.kind = "inferred"`;
- include a confidence between 0 and 1;
- include a short rationale.

Do not invent:

- command names;
- binding names;
- navigation destinations;
- application state;
- data models;
- business rules;
- hidden interactions.

If behavior is plausible but unsupported, add an `unresolved` item instead of asserting it.

### Pass 7: Add supported relationships

Allowed v0.1 relationships:

- `contains`
- `instance-of`
- `variant-of`
- `uses-token`
- `has-state`
- `navigates-to`
- `triggers`

Only use `navigates-to` or `triggers` when supported by source code, explicit interaction metadata, runtime behavior, or explicit user description.

### Pass 8: Canonicalize IDs

IDs should be:

- stable;
- semantic;
- lowercase where practical;
- source-independent when the concept is source-independent.

ID grammar (binding — repeated blind runs drift exactly where this is loose):

- Segments are separated by dots; multi-word slugs use hyphens **within** a
  segment, never extra dots. `component.settings.about.row.platform` is
  wrong; `component.info-row.platform` is right.
- **Canonical component:** `component.<slug>` — two segments, no screen
  prefix (`component.info-row`, `component.metric-card`).
- **Component instance:** `component.<canonical-slug>.<instance-slug>` —
  three segments (`component.info-row.platform`).
- **Every other node:** `<type>.<scope-slug>.<element-slug>` — exactly three
  segments, where scope is the screen slug or a section/region slug
  (`control.profile.save`, `content.about.version`, `state.profile.saved`,
  `token.spacing.16`, `token.color.surface1`).
- **Screen:** `screen.<slug>` — the slug is the declared page name,
  slugified, minus a trailing "Page"; when that result is generic
  (`main`, `home`, `index`, `shell`), prefix the app slug
  (`MainPage` in the Caffe app → `screen.caffe-main`). Scope slugs in
  other ids follow the same choice.
- When the source declares a name (`x:Name`, Figma component name), slugify
  it for the element slug instead of inventing a synonym.
- A **source-declared reusable control** (UserControl / custom control) is
  always a `component` — even when interactive; its interactive nature goes
  in `role` (`component.brew-button` with `role: button`). The `control`
  type is for framework-primitive interactive elements (Button, TextBox,
  ToggleSwitch…) used directly.

Naming vocabulary (use these; do not coin synonyms):

- a bordered/rounded grouping container → `card` — **regardless of its
  visual treatment** (glass, elevated, outlined section panels are all
  `card`; the treatment lives in tokens/styles, not the name);
- a repeated row representing one entry of a collection →
  `<content>-item` (`route-item`, `order-item`; generic fallback
  `list-item`);
- a horizontal label + value pair → `info-row`;
- a stacked label over value → `field` (qualify by content: `path-field`);
- an icon + text low-emphasis button → `action-button`;
- an uppercase small group heading → `section-title` (content node,
  `semanticRole: sectionHeader`).

Extend this vocabulary through eval review, not per-run invention.

Avoid random IDs unless the source has no useful semantic identity.

### Pass 9: Record uncertainty

Use the top-level `unresolved` array when:

- multiple interpretations remain plausible;
- interaction behavior is unknown;
- repeated elements may or may not be one component;
- token semantic naming is uncertain;
- state relationships are ambiguous.

A correct unresolved item is better than a confident hallucination.

### Pass 10: Validate

Before returning:

1. validate against the JSON Schema;
2. ensure every edge `from` and `to` references an existing node;
3. ensure node IDs are unique;
4. ensure no duplicate edges exist;
5. ensure every inferred item has confidence and rationale;
6. ensure no unsupported behavior was invented;
7. ensure repeated patterns were considered for component consolidation.

## Quality priorities

In order:

1. No unsupported semantic claims.
2. Correct hierarchy.
3. Correct repeated-component recognition.
4. Correct state relationships.
5. Useful token normalization.
6. Stable canonical naming.
7. Completeness.

Prefer a smaller accurate graph over a larger speculative graph.

## Stop condition

The graph is complete when it captures the important semantic structure of the supplied UI and remaining uncertainty is represented explicitly.

Do not attempt to model invisible application behavior from a visual design alone.
