# v0.18.262 — Causal Investigator V3 Stage B: witnessed source/coverage ledger

**Type:** Shadow-only evidence provenance architecture. No change to model prompts, tool selection, device control or published answers.

## Real baseline: v0.18.261 (30 October 2026, 21:55–21:56 UTC)
- 24 tools / 11 model rounds / 64.7 s total, 50.3 s provider compute.
- Original draft mentioned nine distinct source-time switch tokens; current safety finalizer replaced it with fixed Historical Journal digest. No existing contradiction flag triggered. A token mention does **not** mean the model's whole narrative was correct.
- Input evidence included original source-time motion and reception-only occupancy, plus app 4013 `setLevel(60)` after target ON. There was no witnessed original ON command or verified upstream execution.
- The outcome remained `unresolved`; `command_history` source class unchecked.

## Design
- New **`causal_witness_ledger.py`** is a pure, bounded, deterministic projection of independently scoped receipts already normalized in `collect_unified_evidence`.
- Every witness carries stable content-derived ID, target/input ID, event class, role, source class and clock provenance. Roles are distinct: state report, issued Hubitat command, independently source-reported input, collector reception.
- For each target, a source coverage matrix separates queried/partial native history, recovered source-time journal, command records, reception copies, app execution not attested, and upstream source not attested. Incomplete pages never prove no activity.
- **Positive attribution control:** An `issued_on` record with a concrete Hubitat `appId` in the same device, followed within 2 s by a source-time ON report, yields `recorded-hubitat-immediate-command`. This is evidence of an immediate recorded Hubitat app command, **not** proof of upstream intention, unique causal responsibility or physical ACK.
- **Negative control:** A `setLevel` after a light ON, a bridge producer, notified listener, collector-only sensor or ON in another device cannot establish that earlier ON's issuer.
- The witness ledger is attached to the shared original-source evidence packet in **shadow mode only**. Terminal Stage A diagnostics gain anonymous counts: `v3_witness_total`, `v3_witness_source_inputs`, `v3_witness_immediate_command_matches`, `v3_witness_targets_without_on_issuer`.
- No additional raw source text, credentials, commands or device names are copied into these metrics. All loops, witnesses, relationships and source-class status lists are bounded.

## Tests
- Positive immediate Hubitat issuer fixture; original cause correctly stays unverified.
- Birthday independent light sequence? No: the generic negative fixture uses a source-timed light ON followed by app level change, ensuring no claimed initiator.
- Same-target timing/order and verified app ID required.
- Journal collector reception excluded from verification; native/archived incomplete coverage not treated as complete.
- Source-only motion retained as an input witness, but correlation remains noncausal.
- Deterministic IDs across receipt order; bounded output retains issuer assessment.
- Legacy terminal fallback and V3 Stage A telemetry unchanged.

## Next (not in this release)
Stage C should turn the coverage matrix into model-visible *feasible source options*, with duplicate/terminal-read tracking and an explicit missing-issuer stop contract. Only after replay tests should the finalizer switch to model-led verified claims.

All CI required before merge; live HA add-on update is a separate user action.
