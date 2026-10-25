# Investigation V2 — staged evidence-first implementation

The merged RFC remains authoritative: [RFC-INVESTIGATION-V2.md](RFC-INVESTIGATION-V2.md).
This implementation is currently a **passive library**. It is not connected
to production HomeBrain request routing, MCP execution or final synthesis.

## Implemented through 0.18.125

- A single canonical case file from timestamped device events and app-log rows.
  Source clocks and offsets are preserved, observations deduplicated by typed
  identity, and separate command versus state stages are maintained.
- An allowlisted adapter for the existing host-produced
  `typed_existing_rule_partial_settings` projection. Its `config_stored`
  records have `time_basis=read_observed_at`: they are values read **now**,
  not proof of installed code's effective semantics on an incident date.
  Credentials, unapproved fields and UI text are never copied to the case.
- Prepared, opt-in schemas for `typed_app_execution` and
  `typed_transport_ack`. These produce distinct epistemic stages **only**
  from successful, explicit, read-only host receipts with verified IDs and
  offset-bearing timestamps. Current production may not yet emit these
  exact types, so the adapters cannot claim unavailable execution evidence.
  Untyped or textual app logs remain mere log statements.
- A bounded *model-proposed* read-plan validator. The model is responsible for
  naming a missing discriminator, information gain and candidate tool. The
  host verifies the tool exists in the current MCP manifest, that its
  operation is explicitly advertised or learned from trusted discovery,
  the arguments match advertised schemas, the target ID was independently
  resolved, and the call is classified as read-only.
- Per-request read caps, exact duplicate prevention, and limited suppression
  of unproductive `hoursBack` growth for already capped history pages. The
  engine **does not execute** these proposals or decide which hypothesis is
  correct. No word-based investigative path or named-device exception is used.

### Contract boundaries

`review_model_read_proposals(...)` accepts `MCPTool` objects returned by
trusted live discovery, `verified_entity_ids` from host resolution and
`learned_operations` only from actual trusted discovery results. **Never**
feed values from an LLM assertion into these host-authority parameters.
Execution must still use the existing MCP executor's permissions, actual
schemas and write confirmation boundary. This library is preflight only.

`source_complete` requires independent, explicit integrity and completion
proof. Pagination reaching a requested date or requesting more hours does
not establish an uninterrupted physical-state timeline. The case remains
useful even when the actual cause stays unverified.

## Acceptance / smoke tests

```bash
python -m pytest -q tests/test_investigation_v2_evidence.py
python -m pytest -q tests/test_investigation_v2_adapters_planning.py
python scripts/run_release_gate.py
```

The October overnight fixture is a sanitized representative subset, **not**
the entire device history. Additional tests cover current-versus-historical
config values, log-versus-execution, ack-versus-physical state, malicious or
unknown tool calls, hallucinated targets, duplicated/capped reads and other
device classes without text-route heuristics.

## Phase C: explicit bounded MCP read harness (0.18.124)

`investigation_v2.read_loop.run_read_only_investigation` now accepts an
explicit model-proposal callback, an existing `ToolExecutor` and its matching
live MCP client, plus independently verified entity IDs. It bounds model
rounds, approved reads, the wall-clock deadline and per-read timeout. It does
not add any background work or automatically intercept user requests.

Each approved read is executed by the existing host executor. The raw MCP
payload is not passed into V2's case file: the `receipt_projection` module
only admits ID-matched dated device events, the existing validated partial
app-settings projection and strictly timezone-aware log timestamps. Unknown
source shapes remain unverified. No user-supplied or source-supplied free-form
description or credential is forwarded to the model.

Model hypotheses are *candidates*, accepted with supporting or conflicting
case-file record IDs and a discriminator. The host validates those references
and never upgrades the model's proposed root cause into an independently
verified fact. The original user question is preserved at every round.

This stage is a **manual/test integration seam**. A real proposal-model adapter
and carefully measured V1/V2 read-only shadow comparison are subsequent PRs.
No live HomeBrain routes, automation writes, confirmation or production
final-answer validators are altered.

## Phase C/D: opt-in model-led evaluation (0.18.125)

`V2ModelProposer` reuses the currently configured
`ChatTransport.chat(messages, [])` provider, asks the model for structured
hypotheses and discriminating read proposals, and supplies only host-projected
read tool names/schema (not unmanaged tool descriptions). All JSON plans remain
untrusted and are validated by the existing V2 planner; no native model tool
call grants permissions.

`evaluate_v2_with_model(explicitly_authorised=True, ...)` is an explicit
integration entrypoint combining model planning, a bounded authorised MCP read
loop and a model-backed evidence selection / ranking round. **It is not wired
into the production agent, feature toggles or normal user conversations.**

`assemble_grounded_answer` renders observed event types and source times from
the case file rather than treating the LLM's narrative as verified facts.
All material command events survive even if the model omits their IDs. Possible
explanations remain clearly marked as hypotheses and incomplete historical
coverage stays explicit. The checker exposes model omissions/invalid IDs
without discarding independently supported observations.

The acceptance tests use mocked Ollama HTTP through the **real** ChatTransport
and fake Hubitat MCP reads; no physical devices or hosted providers are called.

## Not yet implemented

1. More verified MCP source adapters; never infer naive native-log timezones.
2. Measured hypothesis usefulness and objective stopping policies beyond
   initial round/read limits.
3. Bounded model-authored prose with atomic claim-to-evidence verification
   and targeted revision rather than final-answer wholesale rewriting.
4. Read-only shadow comparison V1 versus V2, quality/latency scorecards,
   safe feature flag, production cutover and retirement of V1 guards.

Do not claim Investigation V2 already outperforms Claude or changes the live
answer until measured shadow replays and cutover gates are passed.
