# Hubitat MCP AI v2 — native MCP client

Standalone experimental Home Assistant add-on, version **2.0.0-alpha.4**. V2 has its own runtime and data; it does not load v1 routers, causal planners, incident-specific patches, answer rewriting, historical journal or benchmark pipeline. V1 remains separate.

## Architecture and scope

The configured model uses native Ollama-compatible `/api/chat` function calling to discover and operate the connected Hubitat MCP server. V2 presents the full live `tools/list` catalog allowed by that server/token, including read and write tools. There is no frozen HomeBrain tool allowlist, read-only capability filter or handwritten tool schema registry.

- Refresh and paginate the live catalog for each request. Preserve server descriptions, schemas and annotations internally.
- Support gateway schema discovery with empty arguments and invocation with `tool` / `args`, as well as flat catalogs. The server resolves gateway membership and enforces its permissions.
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

Ask/Chat displays the model answer, current tool operation and exact pending confirmation when required. Tool receipts include names, redacted arguments, success, elapsed time and the same bounded/redacted source response delivered to the model. Truncation is explicit. Completed receipts survive later model failures. Receipts are returned to the current browser session; they are not automatically persisted or included in later chat history.

The unchanged v1 external recorder is retained in an independent SQLite file. V2 starts new history; it does not import v1 samples automatically. The AI tool loop does not automatically ingest the recorder database. Diagnostics endpoints and graphs read the local recorder; MCP reads come from the connected server.

## API

- `POST /api/ask`: JSON `{"request_id":"<UUID>","question":"...","history":[]}`. Optional request_id defaults to a generated UUID; supply one to poll or approve. Send header `X-Homebrain-Request: 1` on mutation requests.
- `GET /api/activity/<request_id>`: current operation and pending confirmation.
- `POST /api/activity/<request_id>/confirm`: JSON `{"id":"<pending UUID>","approved":true}` or false, with the same request header. Only a currently pending ID is accepted once.
- `GET /api/status`: configuration status, model and recorder; does not certify live connectivity.
- `GET /api/diagnostics/status`, `/api/diagnostics/history?metric=free_os_mb&hours=24`, `/api/diagnostics/timeline?hours=24`: independent recorder views.

Use Home Assistant ingress; the optional direct port is disabled by default. The custom mutation header prevents ordinary cross-origin forms/scripts from submitting actions; it is not authentication. Keep the direct interface on a trusted network if enabled.

## Validation and acceptance

Mock protocol tests cover full and paginated catalogs, gateway discovery, flat writes, server refusals, catalog refresh, no automatic write retry, human confirmation/decline/expiry and source receipt retention. CI is necessary engineering evidence, not proof of model reasoning or answer quality.

For first live acceptance use an upstream read-only token and ask:
> Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.

Preserve the first answer and receipts. Compare with v1/Claude/Thaura only on matched evidence, time windows and model settings. Control and automation acceptance require separately authorized test operations; no live writes are performed by CI or repository development.

## Upstream and rollback

Skill files are copied unchanged from [kingpanther13/Hubitat-local-MCP-server](https://github.com/kingpanther13/Hubitat-local-MCP-server/tree/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/agent-skill/hubitat-mcp), commit `98bc7ca2d0f1bd2e2857962292b33d83683bc2b0`, with its MIT license. See `skills/hubitat/UPSTREAM.md`.

Stop the v2 add-on to stop further operations. Uninstalling v2 does not undo device actions or automations already created through MCP. Revert the release to restore the prior client; v1 and its data are untouched.
