# Investigation V2 — staged evidence-first implementation

The merged RFC remains authoritative: [RFC-INVESTIGATION-V2.md](RFC-INVESTIGATION-V2.md).
This implementation is currently a **passive library**. It is not connected
to production HomeBrain request routing, MCP execution or final synthesis.

## Implemented through 0.18.123

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

## Not yet implemented

1. Real live MCP read orchestrator and source adapters for all required tools.
   Verify native logging clock timezone at the source before promoting naive
   Hubitat log timestamps; never guess a DST fold.
2. Model-generated hypotheses and iterative tool selection with verified
   information gain and stopping criteria.
3. Grounded, **non-destructive** atomic-claim and evidence-omission evaluator.
4. Read-only shadow comparison V1 versus V2, latency/quality scorecards,
   source-equivalence checks, feature flag, rollout and removal of V1 guards.

Do not claim Investigation V2 already outperforms Claude or changes the live
answer until measured shadow replays and cutover gates are passed.
