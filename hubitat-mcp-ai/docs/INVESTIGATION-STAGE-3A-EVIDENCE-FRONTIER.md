# Stage 3A — source-grounded autonomous read selection (shadow-only)

Version: **v0.18.275**. Based on merged main v0.18.274.

## Design decision: extend, do not replace

Existing `causal_evidence_planner.py`, `causal_upstream_read_frontier.py`,
`causal_source_feasibility.py`, `investigation_checkpoint.py`,
`causal_witness_ledger.py` and the Stage 2 canonical evidence view remain
independent, established components. Stage 3A creates an **adapter** over
existing source feasibility (only for group incidents) and validates additional
model-proposed discriminating source READs against already recorded scopes.

No new evidence graph, hardcoded bathroom-specific reasoning, command executor
or publication template is introduced. The model chooses the question and
tool candidate; the deterministic host layer can only exclude unsafe,
unauthorized, repeated, ungrounded or unbounded candidate shapes. Scores are
explicitly advisory rather than causal confidence.

## Offline API

`build_stage3_read_frontier(receipts, facts=..., model_proposals=...,
available_read_tools=..., max_choices=12)` is a pure, offline projection.

Inputs:
- Previously retained, typed, successful/failed READ receipts.
- Optional existing `collect_unified_evidence` facts (never accepted as
  command authority or alternative scope authorization).
- Bounded model-proposed candidate READs shaped as `{leaf, args}`.
- An **explicit catalog of currently presented READ tool names**. A previously
  successful leaf is not by itself sufficient catalog authorization.

Currently admitted scoped leaves:
- `hub_list_device_events` using a source-attested device ID, optionally
  restricted by validated `since`, `until`, `attribute`, `offset`, `length`.
- `hub_list_device_dependents` using a source-attested device ID.
- `hub_get_app_config` using an app ID independently observed in a command
  issuer or a valid scoped dependency read.

These are Stage 3A *validated schemas*, not a claim that this exhausts all
existing MCP capabilities. Model proposals for other leaves are deferred
until typed schema/authorization adapters are independently reviewed. The
actual agent's live MCP capability/permission checks remain authoritative.
No fabricated leaf or entity is admitted, and no secrets are echoed.

A source-attested **state report** is not a physical acknowledgement; a
`triggered[]` listener isn't a command issuer; a source-qualified sensor
correlation isn't proof of the originating automation. Host-verified app
identities from source command rows and current app dependencies are leads,
not historical rule-branch proof.

## Repeat prevention and stopping

An exact attempted leaf + validated scope/filters fingerprint is never
recommended again within the retained receipt window, whether it succeeded,
returned empty results or failed. A different bounded source history
window/attribute is distinct. The model's claimed priority/score cannot
override the host evidence score. Duplicate proposals coalesce.

There is **no five-call limit**. `max_choices` limits the amount of advisory
output, not tool invocations. Missing candidates produce
`model-discover-new-read-or-report-limits`, **not** a claim that no source,
command or event exists. The model can consult its authorized tool catalog
or provide the best bounded findings and exact missing proof. The original
model loop keeps full authority in this stage, so no active stopping
behaviour is changed.

Safety scope: this shadow module has **no production imports** and performs
no tool calls, network access, file writes, Hubitat or Home Assistant writes,
publisher changes or configuration migrations. Performance is not claimed
improved until a separately controlled runtime shadow trial.

## Regression coverage and next gates

`tests/test_stage3_evidence_frontier.py` checks exact duplicates (including
failures), narrowed-time source reads, issuer-vs-listener distinctions,
spoofed IDs, disallowed leaves, unbounded windows, caller secrets,
20+ distinct reads, deterministic ranking, existing grouped-source
feasibility and heating-app reads.

1. All repository CI, including full Python suite and release assurance,
   must pass on this new branch.
2. Review the supported leaf/argument schemas against the current live MCP
   catalog **before** any model-loop integration.
3. Add Stage 3B domain-diverse fixture scoring and offline parity metrics
   against the old loop, then a guarded shadow observation in production only
   with separately approved deployment. No change is enabled here.
4. After source parity and latency measurements, separately review Stage 3C
   model loop activation and a rollback switch. Keep legacy answer publisher
   unchanged until Stage 4 evidence-validated model-authored narratives.

Rollback: revert this additive PR. No live migrations or deployment to undo.
