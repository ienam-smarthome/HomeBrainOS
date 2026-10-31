# Investigation Stage 2.5: offline shadow comparison

## Stacked review dependency

This change builds on Stage 1/2 foundation PR #1160 (v0.18.273),
not the deployed v0.18.272 main branch. The new PR targets the foundation
branch for review and must not be merged independently into an incompatible
base. The existing live installation is unchanged.

## Invariant: no active runtime path

`shadow_evidence_comparison.py` imports only the Stage 2 canonical model
at module import time. The optional offline benchmark imports the existing
read-only `collect_unified_evidence` only when explicitly called by tests.
No agent, MCP router, Home Assistant startup, Hubitat integration, publisher,
configuration file, or runtime feature switch imports or calls it.

The comparison uses identical already-retained, successful read receipts.
It performs no live calls, network requests, file/database writes or actions.
It cannot publish a natural-language answer and cannot grant causation,
physical ACKs or complete historical coverage.

## Semantics and diagnostics

`compare_shadow_evidence(receipts, legacy_facts, legacy_graph=None)`
returns a bounded JSON-compatible diagnostic with:

- Canonical typed identity/event/coverage record counts, including separately
  counted **source** and **collector-received** clocks.
- Legacy source-typed witness coverage and exact shared observation key matches.
- Legacy witness keys absent from canonical, with capped examples and the total
  mismatch count; extra canonical records are not assumed wrong because
  the legacy witness ledger has narrower scope and presentation caps.
- Target IDs whose *legacy* presentation labels lack independent canonical
  identity proof. This is a diagnostic only: names are not imported from the
  less-strict legacy representation.
- App IDs for explicit command issuers with verified canonical names when
  the legacy incident ledger kept only their numeric app ID. Notified
  listeners are never considered command issuers.
- Journal query gap-count disagreements, explicitly **not** proof of network
  outages, missing device activity, or complete source history.
- Optional legacy single-incident causal graph scope metadata; never conflate
  its single-event scope with the grouped witness ledger.

Comparison keys normalize timestamp strings to UTC without changing their
underlying provenance. For matching **only**, a legacy `hubitat-command`
clock corresponds to canonical `source-reported` (both originate from the
same native command receipt). This is not a source accuracy upgrade.

A result can be `matching-comparable-witnesses`, `divergence`,
`partial`, or `not-comparable`. Even a perfect match only establishes
agreement on compared evidence, not proof of cause, physical operation,
absence of unreturned history, or global equivalence.

## Reproducible baseline and performance

`test_shadow_evidence_comparison.py` replays anonymised five-cycle
lighting, separate source/receiver clocks, named source identities, explicit
command producers versus listeners, corrupted witness rows, journal
gap mismatches, truncated legacy presentation and HVAC-source data.

`benchmark_shadow_replay(receipts, question, iterations=N)` measures
Python-only compute for the existing legacy facts builder followed by
the new comparison on identical fixture receipts, reporting medians.
It **excludes** MCP/model/network latency and is not a live speed claim.

Suggested local command:

```bash
cd hubitat-mcp-ai
python -m pytest -q tests/test_canonical_investigation_foundation.py tests/test_shadow_evidence_comparison.py
python -m pytest -q tests
```

## Stage gate

1. The stacked PR must pass the complete existing CI and new regression tests.
2. Review identity gaps and mismatches before proposing changes to adapters.
3. Confirm no active runtime imports the shadow module.
4. Merge the foundation PR first, then rebase/retarget this change to main
   and verify CI again.
5. Do not enable autonomous evidence planning, model-authored publisher,
   release installation, or production shadow execution in Stage 2.5.

Rollback: close the stacked PR or revert its additive files. No live
configuration or migration rollback is needed.
