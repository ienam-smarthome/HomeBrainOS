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
- The maintained runtime is a flat set of thirteen Python modules under
  `hubitat-mcp-ai/rootfs/app/`. `app.py` owns FastAPI route registration
  directly; there is no `entrypoint.py`, request-layer registry, inheritance
  chain, or runtime route-bridge stack.

## Module map

| Module | Role |
| --- | --- |
| `app.py` | Loads add-on options, constructs the shared services, owns `RequestCoordinator`, and defines `/`, `/health`, `/api/status`, `/api/dashboard`, `/api/tools`, `/api/refresh`, `/api/chat`, and `/api/ask`. |
| `mcp_client.py` | `HubitatMCPClient`, the single JSON-RPC client used for Hubitat MCP access. Defines `MCPError`, `MCPTool`, and `MCPToolResult`. |
| `mcp_agent_orchestrator.py` | `UnifiedMCPAgent`, the native Ollama tool-calling coordinator. It selects and executes tools, records evidence, enforces live grounding, handles confirmations, consumes streamed Ollama responses, and produces final answers. |
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
   where a fixed authoritative answer is sufficient.
6. Remaining requests use the native Ollama tool-calling loop. Every request
   starts with the same bounded registry: deterministic local tools,
   `hub_search_tools`, and the diagnostic gateway when available. Prompt
   keywords do not select remote schemas. When another gateway is needed, the
   model calls `hub_search_tools`; only gateways named by that structured result
   are added to the next model round.
7. A live-read answer requires successful evidence marked
   `supports_live_claim=True`. If evidence cannot be obtained after the allowed
   retry, the agent refuses rather than making an ungrounded live claim.
8. Routine device controls can execute without a second confirmation. Sensitive
   operations, including firmware installation and higher-risk mutations, are
   stored as `PendingConfirmation` and execute only after a valid confirmation.
9. Every actual structured tool call is classified as `read`, `routine_write`,
   `sensitive_write`, or `destructive_write`. This effect drives request-class
   reporting and whether the call must enter the confirmation queue, and is
   attached to evidence for auditability.
10. Prior conversation is limited to the eight newest messages and 12,000
    characters. Across multi-round execution, retained tool-result content is
    capped at 48,000 characters; older results are compacted before newer ones.
    The system policy, current request, tool-call structure, and internal
    evidence receipts remain intact.
11. `/api/ask` returns the message, route, request class, choices, evidence,
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
- Model payloads use bounded prior conversation and cumulative tool-result
  content. Compaction operates on copied request messages and never mutates the
  authoritative in-process transcript or evidence receipts.
- Automation status precedence is deterministic: broken and disabled signals
  are resolved before paused, and `paused=false` alone never proves active.
- Unknown or incomplete status data is labelled `unknown` rather than guessed.
- Firmware installation requires a firmware snapshot reporting an available
  update plus approval through the host confirmation gate.

## Known gaps

- `mcp_agent_orchestrator.py` remains the largest module and still combines
  dynamic discovery, confirmation state, evidence policy, tool execution,
  retries, and final-answer handling. These concerns should be extracted
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

## Bounded model context

The browser and backend retain at most eight prior conversation messages, and
the backend also applies a 12,000-character history budget. Tool results remain
individually bounded and share a 48,000-character cumulative model-context
budget. When that budget is exceeded, the oldest tool result is replaced by a
labelled excerpt before newer results are considered. The original request
transcript remains unchanged for control flow, confirmation state, evidence,
and audit output; only the copied Ollama request payload is compacted.
