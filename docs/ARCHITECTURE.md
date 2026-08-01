# HomeBrainOS architecture

> Rewritten to match the native MCP-agent consolidation on `main` and the
> structured automation-status work in PR #327 (add-on v0.10.250). The previous
> document described the retired pre-consolidation stack (`entrypoint.py`,
> `AskLayerRegistry`, `semantic_home_*`, `control_agent_*`, `fast_fallback_*`,
> and related wrapper families). Use Git history when that implementation is
> needed for reference.

## Current add-on

- `hubitat-mcp-ai/` is the maintained Hubitat MCP assistant.
- The legacy Maker API dashboard and assistant (`homebrainos/`) has been retired
  and removed from this repository.
- The maintained runtime is a flat set of twenty-one Python modules under
  `hubitat-mcp-ai/rootfs/app/`. `app.py` owns FastAPI route registration
  directly; there is no `entrypoint.py`, request-layer registry, inheritance
  chain, or runtime route-bridge stack.

## Module map

| Module | Role |
| --- | --- |
| `app.py` | Loads add-on options, constructs the shared services, owns `RequestCoordinator`, and defines `/`, `/health`, `/api/status`, `/api/dashboard`, `/api/tools`, `/api/refresh`, `/api/chat`, and `/api/ask`. |
| `mcp_client.py` | `HubitatMCPClient`, the single JSON-RPC client used for Hubitat MCP access. Defines `MCPError`, `MCPTool`, and `MCPToolResult`. |
| `mcp_agent_orchestrator.py` | `UnifiedMCPAgent`, the native tool-calling coordinator. It prepares bounded context, supplies resolved facts to focused policies, coordinates approved calls, and produces final answers. |
| `chat_transport.py` | Owns the Ollama HTTP client, provider configuration, request construction, streaming and non-streaming response assembly, idle-stall detection, and client shutdown. |
| `confirmation_policy.py` | Makes stateless confirmation decisions from structured tool effects and proposed action groups, enforces the action limit and unique-session requirement, and renders deterministic queue or cancellation wording. |
| `confirmation_store.py` | Stores short-lived sensitive actions by session, applies TTL expiry, consumes confirmations once, cancels on replacement questions, isolates queued snapshots, and bounds pending-session capacity. |
| `evidence_recorder.py` | Owns request-scoped evidence receipt storage, timestamps, nested argument redaction, effect metadata, immutable output snapshots, and successful live-evidence detection. |
| `grounding_policy.py` | Owns request-local log and live-evidence retry state, exact log-call observation, and deterministic retry/refusal decisions when the model returns no tool calls. |
| `capability_grounding.py` | Detects assistant-generated capability denials, permits one host-driven discovery recovery, and blocks unsupported limitation claims after known gateways were exposed. |
| `hub_info_service.py` | Discovers the unique Hub Information Driver device, issues refresh and update-check commands, performs bounded polling, reconciles cached identity with live state, preserves units, and returns authoritative firmware/resource snapshots. |
| `tool_executor.py` | Dispatches one already-approved local or remote structured call, measures it, normalises success/failure, records its receipt, and prepares bounded model content. |
| `tool_discovery_catalog.py` | Owns the prompt-independent initial registry, declared/available tool state, native schemas, explicit structured gateway parsing, deduplication, and request-local expansion. |
| `automation_status_service.py` | Deterministically reads Hubitat apps and Rule Machine rules, normalises each item to `active`, `disabled`, `paused`, `broken`, or `unknown`, and returns structured `automation_items`. |
| `device_query_service.py` | Read-side queries over the cached device inventory, including filtering, comparison, aggregation, and room-aware reads. |
| `device_control_service.py` | Write-side device commands such as on, off, toggle, and level changes. |
| `device_target_resolver.py` | Resolves natural-language room and device references to concrete candidates using normalisation and token scoring. |
| `device_state_summary.py` | Shared pure helpers for room names, light detection, active lights, active non-light switches, and active-room summaries. |
| `deterministic_tool_presenter.py` | Formats selected tool results into fixed, non-AI-generated answers for common home-state questions. |
| `agent_prompt_policy.py` | Builds the system prompt and renders the optional device and app identity manifests. |
| `request_classification.py` | Provides non-authoritative prompt helpers for presentation and manifest decisions; these helpers never gate read-versus-write behaviour or tool visibility. |
| `tool_registry.py` | Defines local tool schemas and classifies actual structured calls as read, routine, sensitive, or destructive. |
| `webui.py` | Renders the Home Assistant ingress UI, status badges, structured automation rows, controls, speech, clipboard actions, and technical details. |

## Request flow

1. `/api/chat` or `/api/ask` receives a request in `app.py`.
2. `RequestCoordinator` owns the in-flight task for the session. A newer request
   supersedes the previous task, and client disconnects cancel backend work.
3. Read-only automation-status questions are routed directly to
   `AutomationStatusService`. The service reads live app and Rule Machine data,
   reconciles each item deterministically, and returns both a concise message
   and machine-readable `automation_items` without requiring Ollama.
4. Other requests are handed to `UnifiedMCPAgent`.
5. Common home-state questions can use local deterministic tools and
   `deterministic_tool_presenter.py`, avoiding an additional synthesis round
   where a fixed authoritative answer is sufficient. Firmware and hub-resource
   questions use `HubInfoService` to refresh and poll the Hub Information
   Driver before returning a structured snapshot.
6. Remaining requests use the native Ollama tool-calling loop.
   `ToolDiscoveryCatalog` starts every request with the same bounded registry:
   deterministic local tools, `hub_search_tools`, and the diagnostic gateway
   when available. Prompt keywords do not select remote schemas. When another
   gateway is needed, the model calls `hub_search_tools`; only known gateways
   explicitly named by upstream `results[].gateway` (or the compatibility
   `matches[].gateway` form) in a recognised structured result envelope are
   added to the next model round.
7. `UnifiedMCPAgent` bounds the copied model context and hands it to
   `ChatTransport`. The transport sends either a streaming or non-streaming
   native Ollama request and returns one assembled assistant message without
   knowing about Hubitat tools, evidence, or confirmation policy.
8. After the orchestrator approves a structured call, `ToolExecutor` dispatches
   it to the matching deterministic local handler or `HubitatMCPClient`, times
   the call, normalises its success state, and bounds the result before it
   enters model context. The same path is used for resumed confirmed actions.
9. Every executed result is handed to `EvidenceRecorder`. It sanitises nested
   arguments, attaches the structured tool effect and timestamp, and keeps
   receipts isolated to the active async request. The orchestrator still
   decides which results may set `supports_live_claim=True`.
10. When the model returns no tool calls, `GroundingPolicy` applies the
    request-local grounding state machine. An explicit log request must have a
    successful `hub_read_diagnostics` / `hub_get_logs` outcome. Other
    non-conversational answers require successful evidence already marked
    `supports_live_claim=True` by the orchestrator. Each unmet requirement gets
    at most one targeted retry; the next empty response is refused rather than
    inferred.
11. Routine device controls can execute without a second confirmation.
   `ConfirmationPolicy` consumes the actual structured tool effect and validates
   sensitive action groups, including the unique-session requirement and
   12-action ceiling. Approved groups are queued in `ConfirmationStore` and
   execute only after a valid same-session confirmation. Invalid follow-up
   wording consumes and cancels the pending action; expired entries are purged
   without execution.
12. Every actual structured tool call is classified as `read`, `routine_write`,
   `sensitive_write`, or `destructive_write`. This effect drives request-class
   reporting and whether the call must enter the confirmation queue, and is
   attached to evidence for auditability.
13. Prior conversation is limited to the eight newest messages and 12,000
    characters. Across multi-round execution, retained tool-result content is
    capped at 48,000 characters; older results are compacted before newer ones.
    The system policy, current request, tool-call structure, and internal
    evidence receipts remain intact.
14. `/api/ask` returns the message, route, request class, choices, evidence,
   optional `automation_items`, model, elapsed time, and add-on version. The
   WebUI renders structured automation rows directly when present.

## Safety and correctness contracts

- All Hubitat access originates from the shared `HubitatMCPClient` created in
  `app.py`.
- Device identity manifests are for name resolution only and are not proof of
  current state.
- Live claims require authoritative tool evidence.
- Mutation success is reported only when the corresponding tool result confirms
  it.
- Tool effects are derived from the declared tool and structured operation
  arguments, never from keywords in the user's prompt. Unknown management
  operations fail closed as `sensitive_write`.
- Initial tool visibility is stable and prompt-independent. Remote gateways are
  exposed only through structured `hub_search_tools` results, keeping the first
  request bounded and preventing keyword routing from becoming a second intent
  system.
- `ToolDiscoveryCatalog` accepts expansion only from explicit upstream
  `results[].gateway` or compatibility `matches[].gateway` fields and resolves
  every name against the server's
  bounded current catalogue. Descriptions, unrelated nested values, unknown
  names, search self-references, and failed search results cannot expose a
  schema. A confirmed action fails closed if its queued tool is no longer
  advertised.
- Model payloads use bounded prior conversation and cumulative tool-result
  content. Compaction operates on copied request messages and never mutates the
  authoritative in-process transcript or evidence receipts.
- Provider transport has no mutation, evidence, routing, or confirmation
  authority. Those policies remain in `UnifiedMCPAgent`; `ChatTransport` only
  sends prepared messages and assembles the provider response.
- `ConfirmationPolicy` owns stateless confirmation eligibility, unique-session
  and group-size validation, and deterministic confirmation/cancellation
  wording. It cannot inspect prompt text, store or consume pending actions,
  expose tools, classify raw calls, or execute an approved action.
- `ConfirmationStore` owns pending lifecycle only: bounded storage, isolated
  snapshots, TTL expiry, single consumption, and cancellation. The orchestrator
  remains responsible for passing structured effects to `ConfirmationPolicy`,
  queuing approved groups, and dispatching confirmed actions through
  `ToolExecutor`.
- `EvidenceRecorder` owns receipt construction and request-local storage only.
  The orchestrator remains authoritative for deciding which executed results
  support live claims and supplies only the resulting evidence boolean to
  `GroundingPolicy`. API snapshots are copied so consumers cannot mutate the
  active audit context.
- `GroundingPolicy` owns retry counters, exact successful-log observation, and
  retry/refusal wording only. It cannot inspect prompts, declare or execute
  tools, classify effects, mark evidence authoritative, alter confirmation
  state, or present a successful answer. Separate instances isolate concurrent
  requests, and log grounding takes priority over unrelated live evidence.
- `HubInfoService` owns Hub Information Driver discovery, refresh commands,
  bounded polling, identity/state reconciliation, unit handling, and snapshot
  shaping only. The orchestrator still controls tool visibility and live-claim
  authority; `ToolExecutor` still owns the outer evidence receipt and bounded
  model payload; the deterministic presenter still owns user-facing wording.
- `ToolExecutor` owns dispatch mechanics only after the orchestrator has
  approved a call. It cannot expose tools, approve mutations, bypass
  confirmation, decide live-claim authority, select retries, or present a
  user-facing result. Confirmed and ordinary calls share its success, failure,
  timing, evidence, and payload-bounding path.
- `ToolDiscoveryCatalog` owns registry mechanics only. The orchestrator remains
  authoritative for deciding when the model may search and how an expanded
  conversation proceeds; `ConfirmationPolicy` decides whether an already
  classified requested call needs confirmation.
- Automation status precedence is deterministic: broken and disabled signals
  are resolved before paused, and `paused=false` alone never proves active.
- Unknown or incomplete status data is labelled `unknown` rather than guessed.
- Firmware installation requires a firmware snapshot reporting an available
  update plus approval through the host confirmation gate.

## Known gaps

- `mcp_agent_orchestrator.py` remains the largest module and still combines
  evidence-authority decisions, loop control, confirmed-action coordination,
  context bounding, and final-answer handling. Transport, confirmation
  decisions, pending-state storage, evidence receipt mechanics, grounding retry
  state, Hub Info refresh/reconciliation, approved-call execution, and discovery
  registry state are now separate; the remaining concerns should be extracted
  incrementally with regression coverage.
- The current bounds are character-based rather than model-token-aware. If
  multiple model families are introduced, token-aware budgeting may provide a
  tighter context limit.
- The browser receives the completed `/api/ask` response rather than streamed
  progress and answer deltas.
- Cancellation is coordinated at the request-task level; lower-level Ollama and
  MCP cancellation should continue to be tested explicitly.
- The repository-level `CHANGELOG.md` and add-on `0.10.x` release notes do not
  use one consistently correlated version scheme.

## Repository hygiene

- `CONTRIBUTING.md` bans new `_final`, `_safe`, `_verified`, and `_v2`-style
  replacement modules unless they remain genuinely distinct live capabilities.
- `tests/test_repository_hygiene.py` checks for prohibited suffix families and
  case-insensitive duplicate module names.
- Run `scripts/analyze_imports.py` and `scripts/validate_addon.py` when changing
  the app directory.
- Run the blocking release gate and focused tests before merging.
- Confirm the live import graph before moving or deleting code, port required
  safety checks first, update importers, and delete the superseded module only
  after no production or test importer remains.

## Tool-call-driven mutation safety

No text-based intent classification may gate control-versus-read behaviour.
Mutation gating is checked when the actual tool call is received. The structured
tool-effect registry is authoritative for mutation classification and sensitive
confirmation. Known structured sub-operations override broad gateway hints, so
read and routine calls are not over-classified; unknown management operations
fail closed as sensitive writes. Read and diagnostic answers use gathered
evidence even when their wording contains control verbs. Live-state claims still
require successful evidence with `supports_live_claim=true`.

## Lean tool discovery

No raw prompt keyword or regex matcher may decide which remote MCP schemas the
model can see. The first tool registry is a small, fixed set of deterministic
local tools plus discovery and diagnostics. Additional remote gateways enter the
registry only when a successful `hub_search_tools` result names them. Discovery
receipts are auditable but do not themselves support a live-state claim. Once a
gateway is discovered, its actual structured call is still subject to the
tool-effect and confirmation contracts above.

The discovery parser mirrors the upstream wire contract: `hub_search_tools`
returns `query`, `resultsCount`, `totalToolsSearched`, and `results[]`; each
callable hit names its sub-tool in `tool` and its declared category gateway in
`gateway`. Only that explicit gateway field can expand visibility. Tool names,
descriptions, `callAs` strings, and arbitrary nested text never can.

Capability limitations are output-grounded as well. If the model proposes an
answer claiming that HomeBrain cannot perform an operation, the host runs one
bounded `hub_search_tools` recovery using the unchanged original user request.
This avoids trusting a model-selected search such as `list apps` for an
unrelated rule-authoring request. Newly exposed known gateways return to the
native tool loop and remain subject to effect classification and confirmation.
If the model repeats the limitation despite those gateways, HomeBrain returns a
neutral structured-action failure instead of publishing a false capability
claim. This policy never uses user-prompt keywords to classify read versus
write behavior.

## Confirmed Rule Machine writes

HomeBrain confirmation and upstream Hubitat authorization are separate gates.
The model proposes a Rule Machine mutation without upstream approval; the host
first validates that the direct gateway payload contains a rule name and an
actual rule change, stores an immutable copy, and asks the user to confirm. Only
after that approval does the confirmation policy add the nested `confirm:true`
required by `hub_set_rule`. A no-argument management-gateway call is classified
as the upstream read-only schema probe. The documented `addTrigger` or
`addAction` `{discover:true}` calls are read-only capability probes. Rule writes
put `name`, `addTrigger(s)`, `addAction(s)`, and `bestPracticeKey` directly in
the gateway `args`; an invented `operation/create/args` envelope is rejected
before confirmation and returned to the model for correction. Stable upstream
shortcut invariants are validated at the same boundary: wall-clock triggers
must use the documented Certain Time shape, mapped switch actions use `action`,
custom driver commands use `runCommand`, and a time window is submitted as two
atomic rules rather than one ambiguous many-trigger/many-action rule. These
checks run again immediately before confirmed replay.

Rule authoring resolves the target with a label-filtered device lookup and
targeted command discovery. It must not load the complete device inventory for
a named target or infer driver commands from a similarly named app.

Confirmation is a structured API state, never a phrase inferred by the browser.
`AgentOutcome.confirmation_required` is true only while the same session has an
immutable pending action group, and `confirmation_count` reports its size. The
WebUI renders the confirmation control only from those fields. A model sentence
containing “please confirm”, “ready to queue”, or “have queued” without a real
tool-call group is returned to the model for correction and cannot create a
button. A bare confirmation with no pending group is rejected before any model
call.

Named-device resolution uses `homebrain_resolve_device`. It performs at most
three targeted label filters (space, hyphen, and distinctive numbered-token
forms), then applies the shared deterministic candidate resolver. This handles
labels such as `Block Tab-S9-FE` from user wording such as `tab s9` without a
full device-manifest read.

Confirmed Rule Machine completion is deterministic. HomeBrain requires a
successful tool result, a returned `appId`/`ruleId`, no partial flag, and no
failed health verdict before saying a rule was created. It reports each rule ID
or each failure directly from structured MCP results; a post-write model answer
cannot turn a probe, error, partial write, or unverified result into success.

## Bounded model context

The browser and backend retain at most eight prior conversation messages, and
the backend also applies a 12,000-character history budget. Tool results remain
individually bounded and share a 48,000-character cumulative model-context
budget. When that budget is exceeded, the oldest tool result is replaced by a
labelled excerpt before newer results are considered. The original request
transcript remains unchanged for control flow, confirmation state, evidence,
and audit output; only the copied Ollama request payload is compacted.
