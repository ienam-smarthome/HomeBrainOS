# HomeBrainOS V2 alpha.95 — classify pre-inference MCP catalog failures

**Date:** 14 November 2026. **Scope:** V2 Preview only. This is an operational evidence-integrity increment, not a hub-load fix or a first-answer model-quality improvement.

## Evidence and decision

A genuinely installed V2 alpha.94 first-answer attempt returned `MCP HTTP 503` in approximately 0.1 seconds, without native tool receipts, server inference timing or a model answer. The private source did **not** establish that the Hubitat hub itself was overloaded, why the MCP request failed, or which native endpoint produced the status. No private request ID, home state, source messages or credentials are added to GitHub.

The public `error="mcp"` response did not distinguish **initial catalog discovery failure before inference** from a later failed MCP read with already-returned evidence. Those two classes must not share the same factual or cost interpretation.

## Implementation

- Within the existing `Agent.answer` initial `mcp.list_tools(refresh=True)` boundary, wrap an `MCPError` in a typed `InitialCatalogUnavailable`; the connected MCP catalog is still refreshed for each Ask and is still authoritative for tool permissions.
- At the existing `/api/ask` failure handler, handle that type **before** the generic `MCPError` case. Return a bounded private `mcp_failure` status with `phase=initial_catalog`, safe `error_kind`, numeric `http_status` only for the strict native `MCP HTTP NNN` pattern, `model_invoked=false`, `native_domain_calls=0`, and `automatic_retry=false`. Include `rounds=0`.
- Public answer text states that catalog access failed before investigation, not that a queried source returned no records. Never echo error bodies, URL/query tokens, request headers or arbitrary exception strings.
- Preserve existing post-catalog model-led source selection, complete native receipts and approvals. A later read that fails inside an investigation is **not** reclassified as an initial failure.
- No startup probes, extra MCP requests, retry/backoff loop, automated hub health assumption, deterministic device planner, model call, writes, V1 changes, cloud routing changes, or provider credit use are introduced by the new error path.

## Fictional regression checks

`test_v2.py` exercises synthetic catalog HTTP 503/401, timeout, transport, malformed catalog and secret-bearing arbitrary error strings through the real `/api/ask` handler. Assert exactly one failed catalog attempt per Ask, zero domain calls, zero model rounds, zero leaked private text, empty tool receipts, unchanged current-request approval lifecycle and correctly typed status. These tests do not connect to Hubitat or a cloud account.

## Acceptance and risks

The code is only a classification of **observed initial failure**. A 503 alone does not prove hub overload, firmware regression, a specific app, or the endpoint responsible. The status must not be added to a denominator of model factual answers. After confirming hub stability independently, start V2 manually and collect a new read-only first answer with original successful receipts, provider metrics, source ranges, no native writes and elapsed time. If the same early error recurs, record the new safe failure status, but do not repeatedly hammer the hub to obtain a pass.

**Release gate:** full V2 Python suite, V2 add-on smoke/build, release metadata/validation and existing approval regressions all green at the final PR head, followed by the merge build. Green synthetic CI does not validate installed model usefulness or hub stability.
