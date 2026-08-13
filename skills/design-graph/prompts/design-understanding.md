# Manual Design Understanding Prompt

Use this prompt while the workflow is still being evaluated. Do not rely on the Skill until repeated tests are stable.

---

Analyze the supplied UI as a design system and semantic product surface rather than as a screenshot or drawing.

Your task is to produce a Design Graph conforming exactly to `schema/design-graph.schema.json`.

Use:
- `references/ontology.md`
- `references/inference-rules.md`
- `references/token-rules.md`

Work in the following passes:

1. Inventory directly observable facts.
2. Establish meaningful structural hierarchy.
3. Detect repeated structures and candidate reusable components.
4. Identify states and stable variants.
5. Normalize recurring design values into candidate tokens.
6. Infer semantic roles conservatively.
7. Create relationships.
8. Record uncertainty.
9. Canonicalize IDs.
10. Validate the result.

Important constraints:

- Do not generate implementation code.
- Do not reproduce meaningless Figma/group wrappers.
- Do not infer application behavior from appearance alone.
- Do not invent bindings, commands, routes, data models, business rules, or hidden state.
- Every inferred fact must include confidence and rationale.
- Prefer `unresolved` over low-confidence assertions.
- Prefer a smaller accurate graph over a larger speculative graph.
- The same conceptual UI shown in loading/empty/error/populated forms should normally be modeled as one screen/component with states, not unrelated screens.
- Repeated structures should be considered for canonical component + instances.
- Preserve source provenance when available.

Return only valid JSON.
