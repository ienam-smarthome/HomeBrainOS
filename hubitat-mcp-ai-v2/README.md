# Hubitat MCP AI v2 — native MCP client

Standalone experimental Home Assistant add-on, version **2.0.0-alpha.8**. V2 has its own runtime and data; it does not load v1 routers, causal planners, incident-specific patches, answer rewriting, historical journal or benchmark pipeline. V1 remains separate.

## Architecture and scope

The configured model uses native Ollama-compatible `/api/chat` function calling to discover and operate the connected Hubitat MCP server. V2 presents the full live `tools/list` catalog allowed by that server/token, including read and write tools. There is no frozen HomeBrain tool allowlist, read-only capability filter or handwritten tool schema registry.

- Refresh and paginate the live catalog for each request. Preserve server descriptions, schemas and annotations internally.
- Support gateway schema discovery with empty arguments and invocation with `tool` / `args`, as well as flat catalogs. The server resolves gateway membership and enforces its permissions.
- Validate calls against the live input schema, with no remote schema fetches. For gateway-shaped schemas, reject a selector incorrectly nested inside `args` with an actionable error; do not silently rewrite it. Empty discovery and valid gateway/flat calls remain supported.
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
