# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.10.289**.

## Architecture

FastAPI sends requests to the production `homebrain_agent.UnifiedMCPAgent`,
which preserves the established unified tool loop while delegating no-more-tools
final synthesis to `FinalAnswerCoordinator`. A `ToolDiscoveryCatalog` supplies
a fixed initial registry and expands it only from explicit structured gateway
matches. Deterministic device resolution and history are always present in that
registry; discovery cannot replace a local bounded adapter with the broader
gateway that hosts its upstream operation. Ollama Online selects native calls,
which run through `ToolExecutor` and `HubitatMCPClient`. Request-scoped evidence
receipts are sanitised and isolated by `EvidenceRecorder`; `GroundingPolicy`
allows at most one evidence or log retry before a deterministic refusal. No
regex router or prompt-keyword tool gate controls read-versus-write behaviour.

`ConfirmationPolicy` makes bounded decisions from structured tool effects;
sensitive MCP mutations require an explicit, session-scoped confirmation kept
by `ConfirmationStore`. Read-only and routine gateway operations do not require
confirmation.

After a valid confirmation is consumed, `ConfirmedActionCoordinator`
revalidates and executes the immutable action group. Rule Machine writes are
sequential, fail closed on the first unverified result, and use deterministic
ID-and-health reporting rather than model-generated success claims.

`ModelContextPolicy` applies the conversation-history and cumulative
tool-result budgets to copied provider payloads. It never mutates the
authoritative transcript, evidence, confirmation state, or tool results.

Common daily Rule Machine windows are compiled by `RuleAuthoringService`, not
by model-generated JSON. It uses bounded target lookup, shared fuzzy-safe name
resolution, advertised-command verification, duplicate checks, two atomic
rules, the normal structured confirmation gate, and healthy-result
verification. Advanced rule shapes continue through native MCP discovery.

Hub firmware and resource questions use `HubInfoService`, which refreshes the
Hub Information Driver, polls a bounded number of times, reconciles its cached
identity with live attributes, and returns one authoritative structured
snapshot.

Named-device history questions use `DeviceHistoryService`. It resolves one
device through the shared fuzzy-safe resolver and reads a bounded, optional
attribute-filtered event window from Hubitat. Reported transitions are treated
as evidence of what changed, never as proof of who or what caused the change.

## Setup

1. Install and configure `MCP Rule Server` on Hubitat.
2. Copy its local MCP endpoint and token.
3. Create an API key in your ollama.com account.
4. Configure the add-on:

   ```yaml
   hubitat_mcp_url: http://192.168.1.100/apps/api/123/mcp
   hubitat_mcp_token: YOUR_HUBITAT_TOKEN
   ollama_direct_cloud_enabled: true
   ollama_direct_cloud_base_url: https://ollama.com
   ollama_direct_cloud_api_key: YOUR_OLLAMA_API_KEY
   ollama_direct_cloud_model: gemma4:31b
   require_sensitive_confirmation: true
   ```

5. Start the add-on and open its Home Assistant sidebar panel.

The add-on uses authenticated Home Assistant ingress. Its direct host-port
mapping is disabled by default so the control API is not exposed to the local
network independently of Home Assistant. Do not enable a direct port mapping
unless an authenticated reverse proxy or equivalent access control protects it.

The WebUI includes live dashboard tiles, smart-home shortcuts, typed and spoken
queries, optional read-aloud answers, response metadata, copy, and expandable
technical details.

## API

These endpoints are intended to be reached through Home Assistant ingress:

- `GET /api/status` — MCP and Ollama Online readiness
- `GET /api/dashboard` — cached live-state dashboard counts
- `POST /api/ask` — process a request through the unified MCP agent
- `POST /api/chat` — compatibility alias for `/api/ask`
- `POST /api/refresh` — refresh MCP tools and device manifest
- `GET /health` — add-on health probe
