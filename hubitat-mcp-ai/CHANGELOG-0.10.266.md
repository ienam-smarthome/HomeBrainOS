# Hubitat MCP AI 0.10.266

- Replaced prompt-keyword tool selection with a stable, bounded initial tool
  registry.
- Added remote gateway schemas only after structured `hub_search_tools`
  discovery results name them.
- Kept deterministic local reads, routine controls, and diagnostics available
  without sending the full remote registry to the model.
- Preserved tool-call-driven mutation classification and confirmation after
  dynamic discovery.
- Added regression coverage for registry size, structured expansion, evidence,
  routine-control guidance, and sensitive-action confirmation.
