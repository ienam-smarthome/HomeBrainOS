# v0.18.30 — Claude tool schema preflight and offending-tool identification

## Observed failure
v0.18.29 confirmed `Anthropic HTTP 400; type=invalid_request_error; category=tool-schema`. This is HomeBrain's heuristic classification of a provider error and establishes neither the offending declaration nor a safe remedy. Anthropic requires each custom tool to have a valid `name` (alphanumeric, underscore or hyphen, up to 128 chars) and an object `input_schema`.

## Correction
- Validate tool names for Anthropic's public format, reject duplicates and structurally invalid root `input_schema` declarations locally, **before** any Claude API call. Most importantly, never substitute an empty `{"type":"object","properties":{}}` for a malformed or missing source schema, because that silently widens permitted model arguments.
- Preserve complete original `required`, `properties`, `additionalProperties`, and nested constraints instead of stripping or inventing schemas.
- When Anthropic rejects a submitted tool, privately map a provider-reported `tools.N` or `tools[N]` index to the **prevalidated, locally known declaration name** (for example `tool=hub_read_devices; tool_index=1`). Only the safe tool name and integer index appear in the user-facing error. Never show the raw provider error, schema body, secrets, or prompt/tool arguments.
- The error may remain unresolved until that one precise failure index is observed; do not guess which Hubitat MCP gateway is invalid and do not disable security or change the model or key.
- Free remains default. Claude remains explicitly selected, independently billed, and strict no cross-provider fallback. No Hubitat configuration or device writes.

## Regression
Root-type, malformed properties/required list, illegal/duplicate names, existing required/constraint preservation, tools.N and tools[N] provider paths, out-of-range/tool-message confidentiality, no HTTP call on local rejection. All three CI workflows must pass before merge.

## Next live test
Update HomeBrain to v0.18.30; use explicit Paid Claude with the same request once. If HTTP 400 persists, send the sanitized `tool=` and `tool_index=` fields (if supplied). If no index is returned, the next investigation must request other sanitized provider diagnostics rather than speculatively patch a specific device or rule.
