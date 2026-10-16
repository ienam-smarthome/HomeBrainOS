# 0.18.0 — Scoped app status MCP facade repair

- Fixes v0.17.99 exact-app status reads stopping at discovery: `hub_get_app_config` is a sub-tool, not a top-level MCP tool.
- Discover and invoke the registered `hub_read_apps_code` facade using `{tool: hub_get_app_config, args: {appId, includeSettings: false}}`.
- Updates regression tests to assert the real facade call envelope; preserves explicit incomplete status for missing tools/read failures and keeps all writes disabled.
- No additional Ollama model calls or paid-routing changes.

Current config output remains bounded and may not independently verify every runtime status field.
