# Hubitat MCP AI

Home Assistant add-on providing a native Ollama Online function-calling bridge
to kingpanther13's Hubitat MCP Rule Server.

Current add-on version: **0.10.350**.

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
selects `LiveEvidenceAuthority` through a context-local grounding-policy factory.
The base orchestrator keeps its normal `GroundingPolicy` constructor and direct
base-agent callers retain the original contract. No global module monkey-patch is
used, and concurrent production requests cannot leak recorders or metrics across
request contexts. Grounding retries and refusals are recorded at the authority
decision boundary rather than inferred from final messages. No regex router or
prompt-keyword tool gate controls read-versus-write behaviour.

The production wrapper also owns deterministic live-soak safeguards. Common
routine light/switch commands are sent through the bounded local control adapter
before the model can expand a generic noun into one particular device. Exact
contact-history requests remove presentation-only leading articles before target
resolution, and “why did ... open/close” answers select the relevant contact event
while explicitly stating that event history does not identify causation. Contact
event timestamps are rendered as natural local date and time text while preserving
the authoritative timestamp value and offset. Browser-session history references
support deterministic “before that” and “after that” follow-ups, including
pronoun-only forms such as “When did it open before that?”. Calendar-day filters
count or list yesterday's contact events without model arithmetic or generic event
dumps, and those aggregate/list queries do not replace the last single-event
reference. Ambiguous device choices are retained per browser session, including
choices recovered from deterministic unresolved messages, so a pronoun-only
clarification stays `unresolved` and repeats the choices before any provider call.
Deterministic read and routine-control outcomes use `DirectOutcomeContext` to own
request-local evidence, choices, request class, and mutation state, restoring every
context token on both normal completion and failure.

Contextual current-state follow-ups for temperature, humidity, battery, and power
use the explicitly selected clarification device and bypass provider synthesis.
Active and inactive motion-sensor list/count questions use deterministic live
device filtering, keeping these bounded reads at Hubitat latency with zero model
rounds and zero tool-discovery calls. Room-level attribute reads are intercepted
before the provider loop and filter candidate devices by the requested capability.
Multiple valid sources return deterministic clarification choices, while a single
capable source returns a direct current-state answer. Explicit selection phrases
replace the browser-session target without model involvement, and live values are
refreshed from authoritative Hubitat state before each current-state response.
The WebUI preserves the original requested attribute when a clarification button
is tapped, so selecting a device resubmits a deterministic named-attribute request
instead of a bare label that would enter the model loop. Deterministic operations
within one observed request reuse a single request-local live-device snapshot, so
capability filtering and target resolution do not repeat the same Hubitat inventory
read. Very closely spaced read-only requests may reuse the exact unfiltered live
inventory for at most two seconds; every mutating tool attempt invalidates that
shared snapshot before and after execution, and historical event reads are never
served from it.

`RequestMetrics` wraps the maintained production request path. It records model
rounds, provider time, evidence-backed tool calls, exact tool-discovery calls and
cumulative discovery duration, cumulative remote MCP duration, actual MCP retry
attempts, grounding retries and refusals, confirmation queuing and expiry,
confirmed Rule Machine verification duration, verification failures, ambiguous
and missing device resolutions, cancellation, total duration, and the final
request outcome. Completed-request classification is delegated to the pure
`request_outcome_policy` module, which applies an explicit fixed precedence to
privacy-safe counters only. A grounding refusal is labelled `refused`; a mutation
verification failure is labelled `failed`; a recorded cancellation is labelled
`cancelled`; expired confirmations and deterministic ambiguous or missing device
resolution are labelled `unresolved`. The policy never inspects user or model text.
Local adapters are excluded from MCP timing. Its fixed metric vocabulary rejects
dynamic labels so device names, prompts, credentials, and tool arguments cannot
become metric dimensions. Metrics are returned on the production
`ObservedAgentOutcome` without changing the original result fields.

MCP retries are counted at the transport loop immediately before an actual retry
POST begins. Transport failures and retryable HTTP 5xx responses share the same
counter, while cancellation during backoff does not count a retry that never
started. Retry eligibility remains governed by the existing read-safe transport
policy.

`api_response_builder.build_agent_response` is the live serialization boundary
for `/api/ask`. It preserves the existing response fields, deep-copies evidence
and metrics, supports legacy outcomes without metrics, and never adds prompt,
session, or request identifiers to the response payload. It returns privacy-safe
`metric_rows` plus an optional fixed `outcome_presentation` object containing the
normalised outcome value, human-readable label, and tone token for WebUI styling.
The response includes model metadata only when request metrics confirm at least
one model round, so deterministic responses no longer imply that Gemma participated.

`technical_metrics_presenter.present_request_metrics` converts only the fixed,
privacy-safe request metric vocabulary into compact technical-detail rows. It
reads the production `counters` and `timings_ms` maps, omits zero or unavailable
values, and ignores unknown keys so prompts, device names, session identifiers,
tool arguments, and dynamic labels cannot become visible metric rows. The same
module exposes a fixed outcome-presentation contract for the five supported
request outcomes, giving WebUI rendering stable labels and tone tokens without
duplicating outcome policy in JavaScript.

The WebUI consumes only that fixed `outcome_presentation` object and renders a
compact response badge for success, unresolved, refused, cancelled, and failed
outcomes. Labels are inserted with DOM `textContent`, tone classes are restricted
to the fixed positive, warning, neutral, and critical vocabulary, and legacy
responses without outcome metadata continue to render normally.

`ProviderTokenEstimator` supplies deterministic, dependency-free approximate
token counts for known model families and a conservative default profile.
`TokenAwareModelContextPolicy` applies those estimates only as an additional
stricter production ceiling. Existing configured character limits remain hard
caps and direct base-agent callers retain the original `ModelContextPolicy`.

`ConfirmationPolicy` makes bounded decisions from structured tool effects;
sensitive MCP mutations require an explicit, session-scoped confirmation kept
by `ConfirmationStore`. Expired pending confirmations are removed and counted at
the store boundary; a normally returned expired confirmation is classified as
`unresolved`, while read-only and routine gateway operations do not require
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

Resolved device targets preserve structured measurement units from Hubitat and
supply conservative standard units for common attributes when the gateway omits
them. This keeps named temperature, humidity, battery, and power answers tied to
explicit evidence rather than model inference.

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
queries, optional read-aloud answers, outcome badges, response metadata, copy,
and expandable technical details.

## API

These endpoints are intended to be reached through Home Assistant ingress:

- `GET /api/status` — MCP and Ollama Online readiness
- `GET /api/dashboard` — cached live-state dashboard counts
- `POST /api/ask` — process a request through the unified MCP agent
- `POST /api/chat` — compatibility alias for `/api/ask`
- `POST /api/refresh` — refresh MCP tools and device manifest
- `GET /health` — add-on health probe
