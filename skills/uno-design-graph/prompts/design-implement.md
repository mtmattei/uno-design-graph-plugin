# Design Graph Implementation Prompt

Use this prompt only after a Design Graph has been generated and validated.

---

Implement the supplied UI using the Design Graph as the semantic source of truth and the supplied visual/design source as the visual reference.

Rules:

1. Preserve the graph's hierarchy, component boundaries, states, semantic roles, and token relationships.
2. Do not invent application behavior that is unresolved in the graph.
3. Reuse canonical components where the graph contains `instance-of`.
4. Implement graph states as states of the same conceptual screen/component unless the target framework requires a different internal structure.
5. Preserve token consistency rather than copying raw values independently.
6. Treat inferred graph facts according to their confidence. If a low-confidence inference conflicts with stronger source evidence, prefer the stronger evidence.
7. Do not silently resolve `unresolved` items unless implementation requires a choice. If required, document the assumption.
8. Keep implementation-specific details out of the Design Graph unless separately producing an implementation mapping artifact.

9. When the target framework is Uno Platform and an Uno docs MCP server is
   available, initialize its usage rules (`uno_platform_usage_rules_init`)
   and ground framework idioms via `uno_platform_docs_search` — style/resource
   discipline, control choice, theming. See `docs/uno-mcp-integration.md`.

For A/B evaluation, use the same model, target framework, design input, and implementation instructions as the direct-design baseline. The only changed variable should be the presence of the Design Graph. Tooling access (including docs MCP servers) must be identical across arms.
