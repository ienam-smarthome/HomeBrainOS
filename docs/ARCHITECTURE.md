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
- The maintained runtime is a flat set of eleven Python modules under
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
6. Remaining requests use the native Ollama tool-calling loop. The agent builds
   a query-scoped system prompt, exposes an approved tool set, executes selected
   tools through the shared `HubitatMCPClient`, and records an evidence receipt
   for every call.
7. A live-read answer requires successful evidence marked
   `supports_live_claim=True`. If evidence cannot be obtained after the allowed
   retry, the agent refuses rather than making an ungrounded live claim.
8. Routine device controls can execute without a second confirmation. Sensitive
   operations, including firmware installation and higher-risk mutations, are
   stored as `PendingConfirmation` and execute only after a valid confirmation.
9. Every actual structured tool call is classified as `read`, `routine_write`,
   `sensitive_write`, or `destructive_write`. During the shadow phase this
   effect is attached to evidence and compared with the legacy mutation gate;
   disagreements are logged but do not change execution or confirmation.
10. `/api/ask` returns the message, route, request class, choices, evidence,
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
- Automation status precedence is deterministic: broken and disabled signals
  are resolved before paused, and `paused=false` alone never proves active.
- Unknown or incomplete status data is labelled `unknown` rather than guessed.
- Firmware installation requires a firmware snapshot reporting an available
  update plus approval through the host confirmation gate.

## Known gaps

- `mcp_agent_orchestrator.py` remains the largest module and still combines
  classification, tool selection, confirmation state, evidence policy, tool
  execution, retries, and final-answer handling. These concerns should be
  extracted incrementally with regression coverage.
- Conversation and tool-call messages can grow across long multi-round sessions;
  a bounded history policy is still needed.
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
tool-effect registry is currently observed in shadow mode while the existing
tool-call gate remains authoritative; a later release may cut over only after
the disagreement tests and live telemetry are reviewed. Read and diagnostic
answers use gathered evidence even when their wording contains control verbs.
Live-state claims still require successful evidence with
`supports_live_claim=true`.
