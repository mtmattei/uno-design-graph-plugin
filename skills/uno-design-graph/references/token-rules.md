# Token Extraction and Normalization Rules

## Goal

Capture recurring design rules without overfitting every raw value into a token.

## Candidate categories

- color
- spacing
- typography
- radius
- border
- elevation
- size

## When to create a token

Create a token when at least one is true:

1. The source explicitly declares a token/style/resource.
2. The exact value recurs across semantically related UI.
3. A small cluster of near-equivalent values clearly represents one design rule.
4. The value is important to downstream design consistency.

Do not tokenise every one-off measurement.

## Scope (v0.2 — binding)

A screen graph's tokens are limited to values the modeled surface **actually
consumes**, directly or through a style it uses. Criterion 1 above is
necessary but not sufficient: a declared resource that the modeled screen
never references does not belong in the screen's graph. Do not enumerate
whole style dictionaries or palettes — a complete design-system inventory is
a separate design-system graph. (Blind evals showed generators emitting
~3× the consumed token set by walking the full dictionary.)

## Variant folding (v0.3 — binding)

Interaction-only variants of a base value — hover/pressed shades, alpha
steps of an accent brush, focus tints — are style internals. Tokenize the
**base** value only; the variants live in the design-system layer. Distinct
*emphasis levels the resting surface visibly uses* (label color vs value
color) remain separate tokens.

## Attachment (v0.3 — binding)

`uses-token` attaches to the canonical component, or to the screen for
page-level values — once per token per concept. Never wire token edges
per-instance or per internal part; instances inherit the canonical's tokens.
Attach to an instance only when it **overrides** the canonical value (then
the edge documents exactly that override).

## Naming

Prefer declared semantic names:

`token.color.brand-primary`

If semantics are not known, prefer neutral canonical names:

- `token.color.ff6750a4`
- `token.spacing.16`
- `token.radius.8`
- `token.font-size.14`

Never invent names such as `BrandPrimary` merely because a color looks prominent.

## Value normalization

Normalize equivalent representations before detecting repetition.

Examples:

- `#6750A4`
- `#6750a4`
- `rgb(103, 80, 164)`

may be derived as the same color value.

Do not merge perceptually similar but measurably distinct values unless there is strong evidence they represent accidental drift.

## Spacing

Prefer observed/declared spacing values.

When geometry is estimated from a screenshot, lower confidence accordingly.

Do not infer a full spacing scale from one or two gaps.

## Typography

A typography token may include:
- family;
- size;
- weight;
- line height;
- letter spacing.

Keep incomplete properties if the source does not expose all values.

## Connecting tokens

Use `uses-token`.

Example:

`component.metric-card -> uses-token -> token.radius.12`

For v0.1, `uses-token` may include an edge property identifying what the token controls:

```json
{
  "properties": {
    "appliesTo": "cornerRadius"
  }
}
```
