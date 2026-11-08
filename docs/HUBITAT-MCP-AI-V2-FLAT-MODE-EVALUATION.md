# Hubitat MCP AI v2 — gateway versus native flat MCP evaluation

**Date:** 2026-11-08  
**Production code version:** 2.0.0-alpha.12 (unchanged for this evaluation)  
**Decision:** The upstream server ALREADY exposes native flat leaves when `Consolidate tools behind category gateways` (`useGateways`) is OFF. **Do not introduce a v2 client-side gateway-to-leaf proxy.** First compare a genuine upstream flat catalog with the existing gateway catalog under authorised, read-only conditions.

## Code-grounded findings

The upstream source is `kingpanther13/Hubitat-local-MCP-server`, `hubitat-mcp-server.groovy`, at main SHA `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0` on 8 November 2026.

- The server settings page exposes the **Consolidate tools behind category gateways** toggle. ON by default, `getToolDefinitions()` returns category gateways and core tools; OFF returns all *visible* original leaf definitions, including complete flattened `inputSchema` property metadata, and omits `hub_search_tools` (source around lines 423–425, 6730–6810).
- `tools/list` has the same client-specific Read/Write master and advanced override filters in either mode; the native server dispatch still enforces its own access controls. Flat mode is **not** read-only by itself. Use a genuinely upstream read-only client token for this evaluation.
- Flat mode disables gateway-name calls. The upstream server explicitly refuses a cached gateway call and tells the client to refresh `tools/list` (around lines 7239–7255). V2 already calls `list_tools(refresh=True)` for each request and executes advertised direct tools with their native schema; see `rootfs/app/mcp.py` and `rootfs/app/agent.py`. No v2 runtime changes are needed.
- The upstream README describes approximately **36 gateway-mode items versus 115 flat tools** in its published reference configuration. Actual visible counts depend on installed version, token, per-tool overrides and developer/settings switches. A larger native flat catalog may increase model prompt processing and may reach Hubitat's documented response-size guard (~124 KB), even with flat-mode description trimming. Faster or more accurate results are **hypotheses**, not verified facts.
- This toggle is **hub/app-wide**, not a per-client switch. Changing it can change what OTHER connected MCP clients see and may require each client to reconnect/refetch tools. The flat-mode experiment must not be performed without accepting that disruption. It does not switch the permission masters or grant forbidden operations, but broadens the set of individually advertised allowed tools.

## Existing v2 support — synthetic compatibility tests only

`hubitat-mcp-ai-v2/tests/test_flat_mode_compatibility.py` uses mock MCP `tools/list` and `tools/call` responses to exercise **both catalog forms** with exactly the same underlying simulated `hub_get_logs(mode='hubEvents')` result.

| Property | Gateway ON | Native flat OFF |
| --- | --- | --- |
| Advertised model function | `hub_read_diagnostics` | `hub_get_logs` |
| Model call parameters | `{"tool":"hub_get_logs","args":{"mode":"hubEvents"}}` | `{"mode":"hubEvents"}` |
| First use of a leaf | May fetch `hub_read_diagnostics({})` for leaf metadata | Schema already on `tools/list` |
| Direct leaf-specific parameter validation | Available after metadata discovery | Available before first direct call from the catalog |
| Permission source | Native server masters/overrides | Same server masters/overrides |
| Confirmed writes | Existing UI confirmation + upstream gate | Same existing UI confirmation + upstream gate |
| Expected model-context size | Smaller tool catalog | Larger tool catalog |
| Real Gemma first-answer success and latency | Measured only by installed run | **Not yet measured** |

No device or Rule Machine was modified by the synthetic test. A successful stub response is not evidence of actual `gemma4:31b-cloud` performance.

## Controlled A/B live test (requires separately authorised server setting change)

**Do not let the assistant change the Hubitat server setting automatically.** The comparison cannot be completed from GitHub alone: the repo connection cannot read or operate the installed private hub.

1. Save the current `useGateways` value and client settings/permissions. Confirm the TEST client's read-only master is enforced; do not test writes, enable developer tools or grant access.
2. With **Consolidate tools behind category gateways = ON** (current baseline), refresh/reconnect the v2 MCP client or restart the v2 add-on, open a fresh UI conversation and run G1 and G2 from the frozen acceptance matrix unchanged. Export first-answer Technical JSON for each. Repeat each three times if practical; count every first attempt, including failures, and do not coach corrections. Record the installed version/model/connection and any relevant changes to hub events.
3. At an approved quiet time, set **Consolidate tools behind category gateways = OFF** in the upstream Hubitat MCP Server app. This is a **global catalog-shape change**: connected clients may temporarily fail until refreshed. Do NOT toggle the Read or Write masters, tools or credentials. Reconnect v2 so it fetches fresh `tools/list`, then run precisely the same questions and exports in new conversations.
4. Compare direct-call structure, first-attempt argument success, local `contract_error`, native `isError`, metadata-only schema fetches, relevant reads, unrelated large reads, model rounds, total wall time, and historical evidence accuracy. Note the number of advertised functions and the total tool-schema payload size if available; never infer their values from the published approximate count.
5. Return **Consolidate tools behind category gateways = ON** (previous value) and refresh/reconnect affected clients. Confirm the original gateway tools return in `tools/list` and normal read-only requests work. If flat mode fails to return a valid `tools/list`, times out, or produces model/API context-length errors, restore ON immediately.

### Frozen uncoached questions

**G1:** Investigate the most recent Hubitat reboot. Determine whether it was caused by critically low memory, a firmware update, or another cause. Check available system events and diagnostics. Distinguish verified evidence from possible explanations. Do not change anything.

**G2:** Retrieve the most recent five events for Hallway Light 1, including timestamps and event provenance. Distinguish the reporting device from any proven initiating command. Do not change anything.

## Decision gate

Do not ship a new v2 tool-selection adapter or make flat mode the default based on mock CI or a single fast answer. Prefer **native flat mode** only if its installed read-only trials yield better *first-answer* correctness and argument accuracy with acceptable prompt size and wall time, while preserving access/approval and successfully restoring/reconnecting the other MCP clients.

Otherwise retain gateway mode and focus on source reasoning and completeness. Where one choice changes source coverage or hub events, document that difference instead of attributing it to the model. This is an evidence-quality comparison, not a benchmark of hidden household configuration or private tokens.
