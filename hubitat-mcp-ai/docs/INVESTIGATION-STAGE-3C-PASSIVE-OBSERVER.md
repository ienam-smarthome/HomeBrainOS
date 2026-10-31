# Stage 3C — passive model-loop observation, OFF by default

Source version: **v0.18.277**. Based on merged v0.18.276.

## Scope

The existing `mcp_agent_orchestrator.UnifiedMCPAgent` remains authoritative
for the model's MCP tool choices, gateway compatibility, duplicate prevention,
permission/confirmation checks, read execution and final answer. Stage 3C
adds only a bounded read-only *observer* after a model tool response and
before the original unchanged calls are processed.

Agent constructor parameter `stage3_shadow_mode` accepts only the exact
value `observe`; any other value, including the default `off`, leaves
observation disabled. No Home Assistant add-on configuration, environment
variable, API request, dashboard setting or UI control exposes this flag.
Production Home Assistant continues to construct the agent without it, so
the observer is **not activated by this PR**.

`stage3_loop_shadow.observe_stage3_model_round(receipts, calls, schemas)`
is a pure adapter. It examines up to 16 model-proposed calls against the exact
current round's read gateway schema enums; it never trusts free-text gateway
descriptions, an unadvertised read operation, a tool that merely succeeded in
a previous round, or model text as an operation permission. For recognised
scoped leaf/argument shapes it invokes the existing Stage 3A planner purely
to compare bounded source-backed next-read candidates. No new MCP calls or
additional model rounds are generated.

The diagnostic result contains **counts only**. It cannot expose raw
device IDs, app IDs, API keys, user prompts, tool arguments, history events
or private source contents. It can note model proposals outside the currently
recognised schema subset without labelling them live-permission violations.
It does not establish a causal initiator, source-clock history completeness,
physical acknowledgement or actual tool/model success.

The orchestrator may increment simple request metrics such as
`stage3_shadow_observed_round` only in explicit observe mode. Every observer
exception is caught and counted; it cannot stop or change a model loop.
No answer content, tool list, message, model schema, execution call,
round budget, completion decision or publisher behaviour is changed.

## Verification

- Default constructor mode is `off`.
- Recognised read operations require positive current model catalog schema
  enums and independently attested source entity IDs.
- Repeated previous failed/exact reads are suppressed in the diagnostic
  candidate frontier, not in the live tool executor.
- Unsupported write gateways, unadvertised mappings, malformed JSON,
  spoofed IDs and secret-bearing arguments cannot be promoted.
- Model tool-call arrays, receipt evidence and catalog schemas are unchanged.
- Truncated observation samples are reported explicitly.
- Entire existing CI suite and release assurance must pass.

## Stage 3C deployment and activation gates (NOT met by this PR)

1. Review actual Hubitat MCP gateway operation enums and permission states
   on a deployment test fixture; don't infer that a read gateway name grants
   every nested operation.
2. Add bounded per-request evaluation telemetry with privacy review, and
   test real multi-domain traces to identify missing validated leaves.
3. Explicitly approve an add-on opt-in setting, fallback and emergency rollback
   before allowing runtime passive telemetry.
4. Only after comparing passive output against production original model
   decisions may a *separate* PR propose changing read selection. Keep
   the existing answer publisher and physical controls unchanged.

This version introduces no active planner/publisher rollout. Closing or
reverting this PR restores identical shipped source. No live changes or
configuration migrations need rollback.
