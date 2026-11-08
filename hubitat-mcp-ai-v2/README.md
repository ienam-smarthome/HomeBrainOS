# Hubitat MCP AI v2 — native MCP client

Standalone experimental Home Assistant add-on, version **2.0.0-alpha.12**. V2 has its own runtime and data; it does not load v1 routers, causal planners, incident-specific patches, answer rewriting, historical journal or benchmark pipeline. V1 remains separate.

## Architecture and scope

The configured model uses native Ollama-compatible `/api/chat` function calling to discover and operate the connected Hubitat MCP server. V2 presents the full live `tools/list` catalog allowed by that server/token, including read and write tools. There is no frozen HomeBrain tool allowlist, read-only capability filter or handwritten tool schema registry.

- Refresh and paginate the live catalog for each request. Preserve server descriptions, schemas and annotations internally.
- Support gateway schema discovery with empty arguments and invocation with `tool` / `args`, as well as flat catalogs. The server resolves gateway membership and enforces its permissions.
- Validate calls against the live input schema, with no remote schema fetches. For gateway-shaped schemas, reject a selector incorrectly nested inside `args` **or duplicated as `args.tool`**, with an actionable local error; do not silently rewrite it or transmit it to Hubitat. Empty discovery and valid gateway/flat calls remain supported.
- Let the model select tools, follow up on evidence and write its answer. Execute calls sequentially; never automatically retry a tool call whose write outcome may be uncertain.
- Load the unmodified upstream `SKILL.md`, `safety-guide.md` and `rule-patterns.md` from the bundled skill directory. These are guidance; the connected server's live schemas and guides remain authoritative. Native Rule Machine/Visual Rules are preferred for new automations; the patterns reference describes the legacy custom-rule engine.
- Calls carrying `confirm=true` (including nested gateway arguments) pause for an explicit decision in the UI. Approval is bound to one exact pending call and request; stale approvals fail. A declined or timed-out call is not executed. The model cannot manufacture approval by setting the flag. Ordinary requested operations follow upstream device-identity and permission rules.
- Retain credential redaction, request deadlines, per-call timeouts and context transport bounds. There is no fixed model/tool round quota or incident-specific investigation recipe.

**This version can perform writes allowed by your MCP connection.** To run a read-only acceptance test, use an upstream read-only client token or disable the server Write master. V2 does not change hub permissions. Server Read/Write masters, per-client access, Advanced overrides, required backups and confirmation flags remain authoritative. Client confirmation does not override a server refusal.

## Setup

Refresh the HomeBrainOS add-on repository in Home Assistant and install/update **Hubitat MCP AI v2 (Preview)**. Start it manually and use sidebar ingress. After updating an already-open older page, close/reopen and refresh it once. The header should show the installed version. A "read-only pilot" subtitle is an old interface; a missing-request-header 403 requires refreshing that page, not changing MCP permissions. V1 may stay installed.

Configure:
- `hubitat_mcp_url`: exact Streamable HTTP endpoint, including its path.
- `hubitat_mcp_token`: token if not already in the endpoint URL.
- `model_base_url`: Ollama-compatible endpoint, e.g. `https://ollama.com` or your local Ollama address.
- `model_name`: a tool-calling model supported by that endpoint.
- `model_api_key`: required for Ollama Cloud; blank for local Ollama.
- Optional recorder: `external_hub_diagnostics_enabled: true` and `external_hub_diagnostics_hub_url: http://HUB-LAN-IP`. Default probe 30s, retention 30d.

Installation, ingress and live model/MCP acceptance remain pending. Dedicated container CI probes amd64 without live credentials; it does not prove aarch64/armv7 deployment.

## Interface and receipts

Ask/Chat displays the model answer, current tool operation and exact pending confirmation when required. Tool receipts include names, redacted arguments, success, elapsed time and the same bounded/redacted source response delivered to the model. Truncation is explicit. Schema-only gateway responses are labeled `tool_catalog` with `operation_executed: false`, and retain their original source inside the model-facing receipt. Local contract errors are marked as rejected before execution. Credential redaction preserves schema property definitions and JSON syntax, including credential-named parameters; actual credential values and samples are removed. Completed receipts survive later model failures. Receipts are returned to the current browser session; they are not automatically persisted or included in later chat history.

The unchanged v1 external recorder is retained in an independent SQLite file. V2 starts new history; it does not import v1 samples automatically. The AI tool loop does not automatically ingest the recorder database. Diagnostics endpoints and graphs read the local recorder; MCP reads come from the connected server.

## API

- `POST /api/ask`: JSON `{"request_id":"<UUID>","question":"...","history":[]}`. Optional request_id defaults to a generated UUID; supply one to poll or approve. Send header `X-Homebrain-Request: 1` on mutation requests.
- `GET /api/activity/<request_id>`: current operation and pending confirmation.
- `POST /api/activity/<request_id>/confirm`: JSON `{"id":"<pending UUID>","approved":true}` or false, with the same request header. Only a currently pending ID is accepted once.
- `GET /api/status`: configuration status, model and recorder; does not certify live connectivity.
- `GET /api/diagnostics/status`, `/api/diagnostics/history?metric=free_os_mb&hours=24`, `/api/diagnostics/timeline?hours=24`: independent recorder views.

Use Home Assistant ingress; the optional direct port is disabled by default. The custom mutation header prevents ordinary cross-origin forms/scripts from submitting actions; it is not authentication. Keep the direct interface on a trusted network if enabled.

## Validation and acceptance

[PR #1528](https://github.com/ienam-smarthome/HomeBrainOS/pull/1528) reproduces the reported nested-selector/schema-corruption failure on the old code before fixing it. Scripted recovery and schema/privacy tests do not prove real-model answer quality.

Mock protocol tests cover full and paginated catalogs, gateway discovery, flat writes, server refusals, catalog refresh, no automatic write retry, human confirmation/decline/expiry and source receipt retention. CI is necessary engineering evidence, not proof of model reasoning or answer quality.

For first live acceptance use an upstream read-only token and ask:
> Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.

Preserve the first answer and receipts. Compare with v1/Claude/Thaura only on matched evidence, time windows and model settings. Control and automation acceptance require separately authorized test operations; no live writes are performed by CI or repository development.

## Upstream and rollback

Skill files are copied unchanged from [kingpanther13/Hubitat-local-MCP-server](https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/agent-skill/hubitat-mcp), commit `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0`, with its MIT license. See `skills/hubitat/UPSTREAM.md`.

Stop the v2 add-on to stop further operations. Uninstalling v2 does not undo device actions or automations already created through MCP. Revert the release to restore the prior client; v1 and its data are untouched.

The answer panel provides **Copy answer** and **Copy technical details**. Technical details retain the original API response and receipts, model, request ID and question, plus browser and server timings. The visible response time includes browser network and waiting time. Copying also supports LAN HTTP where the Clipboard API is unavailable. This UI update does not change prompts, model selection, MCP access or answer generation.

## Alpha.8 — evidence-aware follow-up questions

Alpha.7 sent recent question/answer prose but silently omitted all earlier MCP source receipts. Alpha.8 adds an **ephemeral in-memory server evidence cache** keyed by a cryptographically generated browser-session conversation UUID. Only the server's actual bounded/redacted MCP tool receipts populate it; browser-supplied history cannot insert evidence. For a follow-up, the model receives selected earlier tool names, arguments, result excerpts, source collection times and explicit truncation indicators in addition to the existing conversation prose. **This is prior evidence, not a live snapshot, trusted instruction or permission to act.** Live verification remains required when the user requests current state, device control or checks beyond the earlier source coverage.

The cache is bounded to four turns, ten latest non-catalog tool receipts per turn, 3,200 characters per receipt, approximately 20,000 source characters per follow-up, and 32 concurrent browser conversations. Items expire after 45 minutes of inactivity. No persistent transcript or separate evidence database is created. Restarting the add-on loses the cache; earlier evidence is then re-read as needed. New conversation rotates its UUID and sends a one-time server-side clear request. A prior request's technical JSON download is independent, and the `prior_receipts_used` counter only reports excerpts supplied to the model (not factual correctness). Huge tool results are visibly truncated rather than silently presented as complete.

Alpha.8 leaves the **existing MCP capability and write/confirmation design unchanged**; first-answer evaluation should still use an upstream read-only MCP token. No new v1 planner, model substitution, skill-specific question patch, or recorder modification was introduced.

See `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` for the frozen acceptance protocol. CI exercises synthetic evidence and model stubs, not a real Home Assistant ingress, model comparison or private G06 capture. Install the add-on and collect real first-answer exports before declaring an answer-quality improvement.

## Alpha.9 — complete source index and on-demand prior evidence

A real alpha.8 read-only heating investigation retrieved the main controller's event history, but two follow-ups received only five excerpts from newer sources. The model then falsely stated that no controller history had been retrieved. This is a **source-loss / selection problem**, not evidence that the earlier Hubitat read was absent. The actual user-supplied diagnostic exports remain private.

Alpha.9 separates the compact **source index** from the excerpt budget. Every retained, non-catalog server-origin receipt has a unique opaque ID, original gateway/leaf arguments, success state, collection time, original response size, retention availability, and, when the MCP result contains structured event history, its returned event count and earliest/latest **returned** timestamps. These endpoints describe the retrieved sample, not complete historical coverage. If the index itself exceeds its budget, `source_index_omitted` makes missing items explicit; it never implies that the underlying MCP read was not performed.

A follow-up exposes one **client-owned, read-only** tool, `homebrain_read_prior_evidence(receipt_id, offset?, max_chars?)`, in addition to (not instead of) the connected upstream native MCP catalog. The model can select that tool to retrieve up to 16,000 characters per call from the previous **redacted** model-visible source held locally. An offset/next_offset allows multiple chunks and exact-text reconstruction within the archive boundary. The tool never contacts or mutates Hubitat; it is scoped to the same random browser conversation ID. If the archive was evicted/expired, the index says so and the model must use the native MCP tool, selecting an appropriate historical window to regain coverage. No automatic source replay, question-specific algorithm or v1 planner is introduced.

Limits: four turns, 32 non-catalog source receipts per turn, 3,200-character source previews, approximately 20k characters of source index/previews in initial follow-up context, 320k archived characters per conversation with 90k max per individual receipt, 32 conversations and 45-minute inactivity expiry. Archive eviction retains source index metadata and marks the content unavailable; an oversized source is explicitly flagged. The index and archive live in RAM only, with no persistent history or new API endpoint to fetch the archive directly. The model returns `prior_sources_indexed`, `prior_receipts_used` (number of short excerpts included), and `prior_evidence_reads` (local chunk tool attempts) separately. **None of these counts measures factual correctness.**

The sole client-owned tool is limited to earlier source-data retrieval; all Hubitat reads, writes, native automation and administrative operations remain exposed exclusively through the upstream catalog and its existing permission gates. No changes were made to confirmation or write privileges; use an upstream read-only token for investigative testing. The upstream bundled skill files and external recorder remain untouched.

Installed live alpha.9 reasoning quality is **unverified**. CI tests fake source payloads and mock model tool choices; they do not constitute a real Gemma or G06 replay. Run the acceptance matrix in `docs/HUBITAT-MCP-AI-V2-ACCEPTANCE.md` and export both the first question and the follow-up technical JSON.

## Alpha.10 — general evidence scope and causal uncertainty

The latest alpha.9 read-only investigation reported 11 returned historical events per device from a 48-hour requested window, then labelled platform event retention as the probable cause **without a source that discriminated native retention from endpoint return limits, filtering or reporting gaps**. Direct upstream v5.1.7 source review establishes that `hub_list_device_events` reads the native `/device/eventsJson/{deviceId}` response and then applies filters in the MCP Groovy app. Requesting `hoursBack=48` therefore **does not prove** 48 hours of native events were available. No upstream or hub setting was modified.

Alpha.10 adds a general, domain-independent source-scope sidecar (`client_event_source_scope`) to model-visible MCP responses **only when the returned result actually contains event rows**. It reports returned event count, earliest/latest parseable timestamps, requested lookback and limit, a limit-hit hint (not a guarantee), any upstream truncation metadata, and explicit `false` indicators for causal/retention/completeness inferences that the sampled rows cannot establish. This is **descriptive evidence metadata**, not an automated decision, a claim correction or a history replay. The original redacted MCP `content` and upstream metadata remain intact alongside the new client field; technical JSON and later session memory retain the model-visible source result.

A short generic addition to the existing v2 client skill tells the model to distinguish reported observations, plausible explanations and causes supported by discriminating evidence. It encourages further **read-only** checks where available and explicit uncertainty when evidence cannot distinguish alternatives. It also warns not to project current snapshots onto historical windows. The model still owns its investigation, stopping decision and response. The tool catalog, model configuration, direct MCP tool loop, write permissions/confirmations, external recorder, upstream bundled skill files and v1 remain unchanged. No domain-specific heuristics, new planner, model routing, separate answer-rewriter or extra round/latency mandate was added.

Unit/integration tests cover multiple synthetic event types, zero returned rows, limit-hit flags, mixed time zone offsets, untouched non-event/write results, input immutability and exact model-visible source/technical receipt preservation. **CI passes are not real Gemma evidence-quality acceptance.** For live evaluation, ask a new first-attempt read-only cause question in a different domain (e.g. an offline device or an unexplained hub restart), export technical JSON and check that competing explanations remain unverified until independently distinguished. Do not claim historical retention is proven from the absence of returned rows.

## Alpha.11 — first-call gateway contract accuracy

Installed alpha.10's first-answer hub-reboot test identified the correct 2.5.3.119 update/startup sequence, but required six model rounds. Of five upstream attempts, **three failed** because the model nested the gateway selector in `args`, duplicated it inside leaf arguments, or repeated the same mistake for the diagnostic gateway. The model recovered but paid avoidable time/model-call costs. No live hub state was altered by that read-only test.

Alpha.11 improves **model-facing schema presentation** automatically for any connected MCP tool whose *live* `inputSchema.properties` exposes both `tool` and `args`. It provides an explicit example of the required outer selector/inner leaf-arguments shape, explains `{}` as **catalog discovery only**, and adds field-level descriptions. The model-facing schema marks unexpected top-level fields forbidden because the upstream gateway already rejects them. The gateway leaf enum, existing schema fields, original server catalog and actual MCP validation contracts remain unchanged. **No special-case gateway or leaf names are hard-coded**, and non-gateway tools retain their original presentation.

A second generic preflight rejects `args.tool` for live gateway-shaped schemas **even when the outer `tool` is also provided**. Previously that invalid duplicate could reach the native server and generate an avoidable `isError`. Now it yields a local `MCPContractError` with no `tools/call` request; valid calls are forwarded byte-equivalent as structured JSON and are never silently rewritten or auto-retried. The model may still make an invalid call, so this does not constitute proof of first-call success with Gemma.

This does **not** change MCP permissions, confirmation semantics, source-evidence scope, the source memory, recorded diagnostics, model/provider, or v1. It adds no automatic tool-selection planner, incident-specific code or artificial model-round quota.

**Acceptance:** on a fresh alpha.11 install, ask the same uncoached read-only system-event/reboot investigation and then an unrelated read-only device-history question. Export both initial technical JSON files. Count model rounds, gateway `contract_error`, native `isError`, `tools/call` executions, latency and grounding quality. The target is **zero first-call gateway-shape errors**, but CI can only verify synthetic presentation and preflight protections, not real Gemma compliance. Preserve any failures in the record.

## Alpha.12 — live leaf-parameter awareness, without a planner

A real installed alpha.11 test eliminated gateway selector-placement errors (three to zero) but still sent `hub_get_logs(mode='hubEvents',sortBy='desc')`, which the upstream MCP server rejected because the leaf contract says `sortBy` applies to the device/app runtime-statistics tabs. It also made an unrelated broad recent-log read that took 5.24 seconds. The first answer took 15.44 seconds versus 9.94 seconds on alpha.10 despite fewer model rounds; one matched comparison does not prove a latency trend. Live private JSON is not in this public repository.

Alpha.12 now retrieves the **selected gateway leaf's actual server-advertised `inputSchema` and description** through the gateway's read-only `{}` catalog discovery on its first use. This is generic: the model chooses the gateway and leaf; no fixed map or named-domain logic exists. The client stores the gateway's catalog in memory, with only previously selected leaf schemas added to future model-facing descriptions. Cached definitions are invalidated whenever the connected live `tools/list` catalog changes. A metadata lookup is not a device query or actuation, and `leaf_schema_discoveries` records the additional schema-only requests separately from `tool_calls`.

For selected leaves with a well-formed JSON Schema, the client checks **declared** types, enum, required fields, and other schema constraints **before** the original MCP invocation. Invalid arguments become local `contract_error` receipts and do not execute the native leaf. Valid arguments pass unchanged. Invalid/remote-reference schema definitions are treated as unavailable rather than blocking otherwise permitted server operations; timeout/transport failure during optional discovery likewise leaves the native tool available. There is no automatic retry of any potentially mutating call.

Some upstream constraints, including `sortBy` applying only to certain log modes, are expressed in **field description prose**, not a JSON Schema conditional. The client shows that original prose to the model after retrieving the selected leaf schema; it **does not invent a deterministic mode-specific parser or pretend to reject combinations the native schema allows**. Therefore the first cold-start call may still be rejected by the upstream server when a prose-only restriction is missed. On later model rounds/requests, the cached relevant leaf descriptions are available without new catalog probes. The model can also use native gateway `{}` discovery as before.

A short generic instruction prefers focused, read-only historical sources/time windows over broad unrelated log snapshots. It does not enforce tool selection, invent an automatic investigation plan or claim faster runtime. No new model/provider, separate answer rewriter, question-specific patches, synthetic correction rules, user write permission, confirmation approval, v1 modifications or external recorder changes.

**Acceptance:** run the same first-answer reboot question with read-only permissions and model unchanged, plus an unrelated history question. Compare schema-only lookup count, first-call leaf errors, tool executions, rounds, actual latency and source grounding. The target is fewer native parameter errors and unnecessary log reads; both live quality and runtime remain unverified until the installed alpha.12 run.
