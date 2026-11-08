# Hubitat MCP AI v2 — gateway versus native flat MCP evaluation

**Date:** 2026-11-08  
**Production code version:** 2.0.0-alpha.12 (unchanged for this evaluation)  
**Decision (updated after first live trials):** The upstream server ALREADY exposes native flat leaves when `Consolidate tools behind category gateways` (`useGateways`) is OFF. **Do not introduce a v2 client-side gateway-to-leaf proxy.** Native flat mode is now the **provisionally preferred interface for this installed HomeBrainOS v2 model**, based on three live read-only questions. Retain it for further cross-domain evaluation only after verifying the effective client permissions and impact on other MCP clients; do not make it the universal default on three samples.

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
| Real Gemma first-answer success and latency | One prior matching alpha.12 gateway run (13.779 s, 4/8 successful attempts) | One matching alpha.12 flat reboot run (5.792 s, 1/1 successful attempts), plus two other successful flat questions |

No device or Rule Machine was modified by the synthetic test. A successful stub response is not evidence of actual `gemma4:31b-cloud` performance. **The separate installed exports below are real model observations.**

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

## Live installed observations — three native flat-mode questions (8 November 2026)

The user supplied complete private v2 Technical JSON exports from an installed `2.0.0-alpha.12` Home Assistant add-on using `gemma4:31b-cloud` and the Hubitat MCP Server `5.1.7`. The exports were reviewed outside the public repo. **Only aggregate measurements and generalized findings appear here**; raw household events, tokens, LAN addresses and configuration dumps remain private.

| Live question | UI elapsed | Server elapsed | Model rounds | Model attempts | Successful reads | Local rejections | Leaf-schema discoveries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G1: latest hub restart | 5.792 s | 5.652 s | 2 | 1 | 1 | 0 | 0 |
| G2: latest five device events | 8.815 s | 8.748 s | 3 | 2 | 2 | 0 | 0 |
| G3: most recent OFF cause, automation + sensors | 11.962 s | 11.865 s | 7 | 6 | 5 | 1 | 0 |
| **Total, three questions** | **26.569 s** | **26.265 s** | **12** | **9** | **8** | **1** | **0** |

The single G3 failure was a type mismatch in a direct tool's app identifier (number instead of live-schema string); local preflight rejected it without execution, then Gemma corrected it. **Zero gateway selector/nesting errors** were seen, as expected because flat mode has no nested gateway selector.

For the exactly matching G1 question on **the same installed alpha.12 version and model**, gateway ON had **13.779 s, 4 rounds, 8 model attempts (4 successful/4 rejected), 1 metadata-only catalog discovery**. Flat mode OFF had **5.792 s, 2 rounds, 1 successful attempt, 0 errors and 0 catalog discoveries**. The observed **7.987 s reduction (~58%) is only one paired comparison**, not proof of stable relative speed or a causal performance guarantee. G2/G3 have no matched gateway run on this recorded comparison.

### Model output quality is a separate criterion

- **G1:** Correct update/startup event sequence and earlier memory incidents; the answer still presented the update as absolutely verified and ruled out other interruptions without independent crash/power evidence. Grade: relevant first evidence, **overstated exclusivity**.
- **G2:** Correct latest five device rows, command issuer versus physical state reporter, source roles; the export reports `prior_receipts_used=1`, so this was not fully isolated from prior context (though both live reads were independent). Grade: **supported retrieval/provenance**.
- **G3:** Correct app-issued OFF command, configured 15-second inactive-off action, both motion sensors' inactive transitions, and a 15.128-second last-inactive-to-command interval. This is **strongly supportive**, but no internal app timer callback trace was retrieved. Claims that the callback was explicitly verified and every other potential influence excluded exceed the evidence. Grade: **strong corroborated hypothesis, not internal execution proof**.

No change was made to HomeBrainOS runtime, upstream Hubitat application, Hubitat devices, or repository permissions for this evaluation.

### Permission and other-client gate remains unresolved

The flat-mode exports are read-only *operations*. They **do not independently prove that the connected MCP client is restricted to read-only operations**. A separate earlier diagnostic reported `writeEnabled: true`, but that alone does not establish the effective per-client grants. Before further live testing, verify the test client's actual **effective Read allowed / Write denied** policy in the Hubitat MCP Server client settings; avoid sending a write as a permission probe. Do not publish tokens or detailed client access data. If read-only access is not available for this connection, use a verified read-only test connection rather than trusting natural-language “do not change anything.”

The upstream `useGateways` switch is **server-wide**. Confirm that other connected clients' tool discovery and read-only access still work while it is OFF. Restore the previous ON mode if integrations break, or if testing is concluded without an explicit decision to retain flat mode. The user has already enabled OFF for this comparison; **do not toggle or restore it through repository work**.

## Next frozen cross-domain acceptance — fresh first answers

Preserve exact input questions, export Technical JSON on the first answer, and avoid model coaching, tool-name hints, repeated correction, or changes to the hub's rules/devices. Remain in flat mode for the next tests **only if the actual MCP test client permissions are verified read-only**.

**F1 — Humidity threshold duration (historical range and absence)**
> Investigate the most recent time the Bathroom Meter humidity went above 70%, and identify when it subsequently dropped below 60%. Calculate the elapsed time if the required historical readings are available. Clearly state any missing event coverage or uncertainty. Do not change anything.

**F2 — Heating versus room-demand contradiction (multi-device history)**
> Investigate the most recent occasion when the main Thermostat was heating while the room TRVs appeared not to need heat. Compare their actual historical operating states and setpoints at the relevant times, and determine whether all room TRVs were genuinely idle. Identify evidence gaps rather than using today's readings to infer past conditions. Do not change anything.

**F3 — Competing evidence, different domain (optional)**
> Investigate the most recent occasion a device became offline or unresponsive. Determine which device and what the hub actually recorded, and distinguish any diagnosed cause from possible causes. Do not change anything.

For every run record `ui_version`, `model`, `captured_at`, **client vs server elapsed**, rounds, tool attempts, successful reads, local vs remote errors, `leaf_schema_discoveries`, prior receipts (a carryover makes “fresh first answer” less independent), sources actually covering the focal time, unsupported numerical claims, source-specific data gaps and causal confidence. Repeat G1 and F1 at least twice before inferring stable latency or correctness.

**Current decision:** Keep native flat mode as a **provisional, observed leader** for this user's v2 trial. No new v2 code architecture, router or prompt patch is justified by these exports. A broader and repeatable sample, verified read-only test permissions, and acceptable interoperability are required before calling it the final default.
