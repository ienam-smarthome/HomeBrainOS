# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.10.304**.

## Architecture

FastAPI sends requests to the production `homebrain_agent.UnifiedMCPAgent`,
which preserves the established unified tool loop while delegating no-more-tools
final synthesis to `FinalAnswerCoordinator`. A `ToolDiscoveryCatalog` supplies
a fixed initial registry and expands it only from explicit structured gateway
matches. Deterministic device resolution and history are always present in that
registry; discovery cannot replace a local bounded adapter with the broader
gateway that hosts its upstream operation. Ollama Online selects native calls,
which run through `ToolExecutor` and `HubitatMCPClient`. Request-scoped evidence
receipts are sanitised and isolated by `EvidenceRecorder`; the production agent
installs a context-local `LiveEvidenceAuthority` at the established grounding
boundary so it alone combines current receipts with bounded retry/refusal state.
Grounding retries and refusals are recorded at that decision boundary rather
than inferred from final messages. Direct base-agent callers retain the original
`GroundingPolicy` contract. No regex router or prompt-keyword tool gate controls
read-versus-write behaviour.

`RequestMetrics` wraps the maintained production request path. It records model
rounds, provider time, evidence-backed tool calls, exact tool-discovery calls and
cumulative discovery duration, cumulative remote MCP duration, grounding retries
and refusals, confirmation queuing and expiry, confirmed Rule Machine verification
duration, verification failures, cancellation, total duration, and the final
request outcome. A normally returned request with a grounding refusal is labelled
`refused`, not `success`; this classification uses the fixed refusal counter and
never inspects user or model text. Local adapters are excluded from MCP timing.
Its fixed metric vocabulary rejects dynamic labels so device names, prompts,
credentials, and tool arguments cannot become metric dimensions. Metrics are
returned on the production `ObservedAgentOutcome` without changing the original
result fields.

`api_response_builder.build_agent_response` is the live serialization boundary
for `/api/ask`. It preserves the existing response fields, deep-copies evidence
and metrics, supports legacy outcomes without metrics, and never adds prompt,
session, or request identifiers to the response payload. It also returns
privacy-safe `metric_rows` generated from the real nested `RequestMetrics`
snapshot for stable technical-details rendering.

`technical_metrics_presenter.present_request_metrics` converts only the fixed,
privacy-safe request metric vocabulary into compact technical-detail rows. It
reads the production `counters` and `timings_ms` maps, omits zero or unavailable
values, and ignores unknown keys so prompts, device names, session identifiers,
tool arguments, and dynamic labels cannot become visible metric rows.

`ProviderTokenEstimator` supplies deterministic, dependency-free approximate
token counts for known model families and a conservative default profile.
`TokenAwareModelContextPolicy` applies those estimates only as an additional
stricter production ceiling. Existing configured character limits remain hard
caps and direct base-agent callers retain the original `ModelContextPolicy`.

`ConfirmationPolicy` makes bounded decisions from structured tool effects;
sensitive MCP mutations require an explicit, session-scoped confirmation kept
by `ConfirmationStore`. Expired pending confirmations are removed and counted at
the store boundary; read-only and routine gateway operations do not require
confirmation.

After a valid confirmation is consumed, `ConfirmedActionCoordinator`
revalidates and executes the immutable action group. Rule Machine writes are
sequential, fail closed on the first unverified result, record verification at
that exact boundary, and use deterministic ID-and-health reporting rather than
model-generated success claims.

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
