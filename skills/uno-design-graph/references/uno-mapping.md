# Uno Mapping Layer (`properties.uno`) — v0.6

The Design Graph targets Uno Platform (see the *Target framework* section
of `method.md`). Every node may carry an `uno` object inside its
`properties`, mapping the semantic concept to its Uno/WinUI realization.
Since schema 0.2.0 the layer is typed per node type: unknown keys are
schema errors, so a typo like `xname` fails validation instead of silently
scoring zero on `uno_mapping`. This document is the convention behind
those types.

Evidence discipline applies unchanged: when the source is an Uno app, the
mapping is `declared`/`observed` fact — copy it exactly. When the source is a
design-only input (screenshot/Figma), the mapping is the generator's proposed
realization and the node's evidence must reflect the weakest link
(`inferred`, with rationale). Never invent an `x:Name` or resource key that
no source declares — omit the field instead.

## Fields by node type

### `screen`

```json
"uno": { "type": "Page", "class": "Orbital.Presentation.SettingsPage" }
```

### `component`

- Canonical, source-declared reusable control:
  `{ "type": "UserControl", "class": "Orbital.Controls.PageHeader" }`
- Canonical, style-defined:
  `{ "type": "Border", "styleKey": "OrbitalCardStyle" }`
- Instance: `{ "xName": "ProfileSection" }` (plus overrides only).

### `control`

```json
"uno": { "type": "TextBox", "xName": "UsernameBox" }
"uno": { "type": "Button", "styleKey": "OrbitalPrimaryButtonSm", "xName": "SaveUsernameButton" }
```

`type` is the exact type name with **no xmlns prefix** (`Button`,
`TextBox`, `ContentDialog`, `FontIcon`, `AutoLayout`, `TabBar`). A prefix
like `utu:` is a per-file alias, not a declared identity, so it never
survives a round trip. For anything outside the WinUI namespace, carry the
CLR namespace in `namespace`:

```json
"uno": { "type": "AutoLayout", "namespace": "Uno.Toolkit.UI", "xName": "HeaderLayout" }
```

The semantic `role` field stays lowercase-human (`button`, `textbox`); the
`uno.type` carries the real type. When unsure of the correct Uno control
for a concept, resolve it with `uno_platform_docs_search` rather than
guessing.

### `content`

```json
"uno": { "type": "TextBlock", "styleKey": "OrbitalMonoSmall" }
```

### `asset`

```json
"uno": { "type": "Image", "source": "ms-appx:///Assets/Icons/Uno-logo.png" }
"uno": { "type": "FontIcon", "glyph": "E74D" }
```

### `token`

Preserve the declared resource identity — this is the single most valuable
field for round-trip and codegen:

```json
"uno": { "resourceKey": "OrbitalSurface1Brush", "resourceType": "SolidColorBrush" }
"uno": { "styleKey": "OrbitalCardStyle", "property": "CornerRadius" }
```

Category ↔ resource-type guide: `color` → `SolidColorBrush`/`Color`;
`typography` → `FontFamily` + `TextBlock` style; `radius` → `CornerRadius`
(often a style setter); `spacing` → panel `Spacing`/`Thickness` literal (no
resource key exists unless the source declares one — then keep it);
`elevation`/`border` → style setters. Token **ids** still follow the Pass 8
grammar; when a resource key exists, derive the slug from it
(`OrbitalSurface1Brush` → `token.color.surface1`) so ids stay stable AND the
exact key survives in `uno.resourceKey`.

### `state`

```json
"uno": { "mechanism": "VisualStateManager", "visualState": "Saved" }
"uno": { "mechanism": "code-behind", "member": "AnimationHelper.FadeUp" }
"uno": { "mechanism": "binding", "member": "HasSelection" }
```

`mechanism` is one of `VisualStateManager`, `code-behind`, `binding`,
`storyboard`, `other`. `member` records the driving condition or helper
(the v0.5 condition-vs-presentation rule keys on it).

## Rules

1. **Copy, don't coin.** Declared keys/names/types are copied exactly; the
   mapping layer never re-synonymizes the source.
2. **Omission over invention.** A missing `uno` field is honest; a guessed
   one is a hallucination.
3. **Uno MCP in the loop.** Generators with access to the Uno Platform docs
   MCP use it to resolve control identity, Toolkit component names, and
   theming/resource idioms for the mapping layer (and for nothing in the
   semantic layer — that stays evidence-driven from the design source).
4. **Round-trip contract.** Design → graph → implementation → graph must
   preserve `uno.resourceKey` / `uno.xName` / `uno.styleKey` / `uno.type`
   exactly; drift in this layer is a parity defect, not naming noise.
   `scripts/diff_graph.py <design> <actual>` checks it; see
   `references/runtime-source.md` for building the `actual` graph from the
   running app.
