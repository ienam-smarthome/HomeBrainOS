# Hubitat MCP AI 0.10.272

- Extracted request-local registry state and dynamic expansion into a focused
  `ToolDiscoveryCatalog`.
- Centralised the fixed prompt-independent initial order, available and
  declared tool maps, native schema rendering, deduplication, and expansion.
- Restricted discovery parsing to explicit `matches[].gateway` fields in
  recognised structured result envelopes.
- Prevented descriptions, unrelated nested strings, unknown names, failed
  searches, and the discovery tool itself from exposing remote schemas.
- Made queued confirmations fail closed when their approved gateway is no
  longer advertised before execution.
- Preserved compatibility helpers for the existing initial-selection, schema,
  and discovery test surfaces while routing production state through the
  catalog.
- Kept discovery timing, confirmation decisions, execution, retries, and
  conversation control in `UnifiedMCPAgent`.
- Added direct regression coverage for structured parsing, deterministic order,
  repeated expansion, unavailable tools, schema collisions, and confirmation
  invalidation.
