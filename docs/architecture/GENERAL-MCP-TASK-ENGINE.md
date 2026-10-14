# General MCP task engine — phase 1

## Goal

HomeBrain should interpret user meaning, select skill guidance, discover live
MCP operations, execute under the existing safety gates, and answer only from
real evidence. Avoid adding a new request-word regex or one-off answer repair
for each new phrasing.

## Data flow (opt-in)

1. Existing direct, safety-critical and cheap deterministic paths remain.
2. For other non-conversational requests, `GeneralTaskPlanner` requests one
   structured task proposal from the configured model (no callable tools).
3. `GeneralTaskPlan.from_model` validates domain, operation, bounded
   capability queries and allowed skill domains. Malformed/failed output
   falls back to the current MCP agent.
4. Skill guidance comes from the validated domains; no user-word regex is
   used to select these sections.
5. The first proposed capability query feeds `hub_search_tools`. The live,
   permission-filtered MCP registry and exact remote schema remain decisive.
6. The plan's objective and evidence goals join the system instruction;
   they are explicitly **not** evidence or approval.
7. Existing model-directed tool calls execute via `ToolExecutor`, and
   existing evidence/confirmation/final-answer safeguards remain authoritative.

## Important invariants

- A plan never carries a device ID, MCP arguments, confirm=true or permission.
- Model-classified "write" cannot bypass user approval, permissions or
  source verification. The plan is advisory metadata only.
- No hallucinated tool name is executed from the plan. Gateway names/operations
  come from server discovery and declared schemas.
- A failed/invalid plan is not a user-visible failure and triggers no write.
- Confirmation, backup, request cancellation and existing evidence receipts
  remain unchanged.
- This phase is disabled by default while tests are gathered.

## Cross-domain evaluation before default-on

Use identical hub snapshots, user constraints and tool permissions to compare
HomeBrain with a skill-guided MCP client. Include device controls, rooms,
native automations, classic apps, hub jobs, device provenance and admin.
Measure valid tool selection, false-success rate, evidence coverage, schema
errors, unnecessary calls, latency and post-write verification.

## Subsequent milestones

1. Adaptive per-stage gateway shortlist and multi-capability discovery,
   without exposing the entire 118-tool catalog at once.
2. Typed completion/claim verification across read and write operations.
3. General native automation intermediate representation and validated compiler.
4. Consolidation of redundant phrase-specific handlers after benchmarks
   demonstrate parity; never remove existing safety checks as a shortcut.
