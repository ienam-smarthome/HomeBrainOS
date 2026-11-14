# HomeBrainOS V2 alpha.99 — native history source proof obligations

**Date:** 14 November 2026. **Scope:** V2 Preview only. User's private live source receipts remain outside this repository.

## Source-real reason for this change

An installed alpha.98 exploratory read-only historical state-continuity question completed using two successful native reads and the existing source review/final audit, but the model concluded that a device remained in the same state because no matching transitions occurred in **returned** mixed-attribute rows and the current snapshot showed that state. This is an unsupported closed-world deduction; source coverage was explicitly unverified. No device-change action occurred. In the provided original native tool receipt, the generic client source-scope envelope explicitly marked `can_infer_uninterrupted_state_between_events=false`, `can_infer_requested_window_fully_covered=false` and `can_infer_older_events_absent=false`, but the compact **final audit index** did not carry the first and third boolean, its largest returned-event time gap, or several relevant requested/returned scope fields. The original tool receipts remained available; lack of a prominent index flag is a plausible mechanism for audit failure but not proven as the sole cause.

A count lower than the requested event limit is NOT a guarantee that the native store was exhaustively searched, retained all earlier records, or recorded every physical state transition. Likewise, absence of the exact event name in a returned mixed-attribute page is a bounded observation, not an interval-state proof. The source's `producedBy` field identifies a reporter, not the initiator, and notified listeners are not command issuers.

## Change, bounded by original evidence

- Extend the final audit's existing safe scalar allowlist to retain the **original native source's explicit booleans** for uninterrupted state, requested-window coverage, older-event absence, native-store independent verification, missing-record cause, initiator/reporters and filters; plus requested lookback, limit and largest gap between actually returned events.
- Attach a concise, typed `historical_continuity_proof_obligations` object to an already-successful original `hub_list_device_events` result **only where a relevant boolean is explicitly present**. It is scoped to that specific returned receipt and does not claim the physical device interrupted or remained uninterrupted. If a field is absent, no positive or negative guarantee is invented.
- Strengthen the pre-existing **tool-free source-to-claim final audit**, requiring it to respect source-declared negative proof limits. Explicitly distinguish *no matching transition returned* from *no transition occurred*, and current device state from historical state. Under-limit counts and current ON snapshots do not override a source's negative continuity or completeness flags.
- No source query, extra model round, automatic polling, timeout adjustment, unplanned write, model-provider switch, cloud-credit change, UI redesign or V1 modification. Tool calls, original receipts, interaction approvals, manual paid mode and the existing model-led source choice remain unchanged.

This addresses the concrete upstream-to-audit data-loss in the source contract, not a physical outage diagnosis. It is **not a deterministic semantic postprocessor** and cannot guarantee Nemotron will obey evidence restrictions; that remains a measured installed acceptance gate.

## Synthetic regressions

Pure fictional tests cover full false flag preservation despite 88/100 row-limit metadata, largest returned gap, no matching state event name, native filter/clock values, thermal and motion histories, missing-booleans cases, failed receipts, separate Monitor saved-bin coverage, no credential/sample leakage, and a scripted existing-model final audit offered **zero tools** after one native read. No live hub or model is called by the tests. Regressions use fictional identifiers only.

## Hypothesis, risks, evaluation and rollback

Hypothesis: direct exposure of authoritative negative proof flags to the final model audit will reduce unsupported whole-interval continuity statements while preserving positive returned event chronology. Expected extra data: a few small existing-audit prompt fields, **no additional model rounds or MCP reads**. A failed provider interpretation is still possible. Check token impact in first source-real tests.

Require full V2 Python test suite, container/smoke, UI fixture, metadata and repository CI on final PR head and after merge. Then evaluate a **new** uncoached read-only continuity problem from a different domain using PRIVATE original receipts; verify latest current status is never promoted to whole-period proof, negative event scope never becomes proven absence, reporter/initiator remain distinct, successful/failed calls and actual row bounds recorded, no writes, and source-grounded first-answer quality. Do not reuse the already-exposed case as independent success.

Rollback to the prior V2 release if the index misrepresents source guarantees, adds excessive token overhead, causes approval regressions or fails to improve independent model results. After another measured failure, compare model choices or redesign typed-claim validation before adding more prompt layers; do not cycle through event-specific patches.
