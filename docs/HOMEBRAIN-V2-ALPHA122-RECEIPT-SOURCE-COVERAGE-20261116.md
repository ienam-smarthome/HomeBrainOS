# V2 alpha.122 — original-receipt source coverage at model review

**Status:** code candidate; original source-real acceptance and latency improvement not yet measured. Scope: V2 only; no V1 modifications, new native reads, model routing, rule/device writes or safety bypass.

## Hypothesis

In installed alpha.121 read-only historical tests, factual calibration was generally sound but source reviews spent repeated full model rounds without new evidence. One cross-domain TRV answer tried an unsupported `stateFilter` argument, consumed ten model rounds and an all-device inventory; a straightforward five-event light history consumed five model rounds, including a final model-only audit that added no native observation. The user-facing typed transition output used UTC rather than the configured UK civil time when `hub_timezone` was omitted at the caller.

## Change

1. Before the existing read-only evidence-sufficiency model review, derive a small **navigation ledger** from ORIGINAL current-request successful and failed receipts. It records per-native-read requested dimensions; original returned row counts, bounded value counts by exact event name, source-returned first/last indexed instants, source-advertised query start and row caps; distinguishes transport/schema failures from zero results. It cannot identify command cause, continuous state or full historical coverage. Only safe short enumerated/numeric values are indexed. Original MCP payloads, unfiltered technical receipts and model-choice catalog remain unchanged. Optional Device Monitor catalog exposure is explicitly not a confirmed connection or actual read.
2. This ledger is exposed **at the pre-existing** source-review checkpoint for causal and other historical read questions; it does not create a new model turn, select a read or claim an answer. Repeated idle refreshes remain repeated observations, not transitions.
3. Skip a **second tool-free final audit** for a noncausal historical-measurement answer only when the source-review opportunity already ran, no fresh receipt was added, all original reads succeeded, and at least one original device-event read returned inspectable nonempty **uncapped** event rows. The first review still has full read-only tool choice. A failed/capped/empty read, additional native read or causal review preserves the previous audit path. This is a *round-saving candidate*, not a sufficiency or factual correctness certificate.
4. Typed temporal time presentation now uses the request's resolved configured/hub IANA timezone with Europe/London fallback (GMT/BST), rather than passing an absent raw parameter and silently displaying UTC.

## Recorded source-real baseline (not replayed by CI)

Alpha.121, 16 November 2026, original private receipts:
- Last Livingroom Light 2 ON→OFF: **7/8**; five rounds, about 232k provider-reported input tokens, 30.2s server, two successful read receipts, no causally discriminating second source.
- Bedroom 1 TRV versus main thermostat history: **6/8**; ten rounds, about 792k input tokens, 48.7s server, seven successes and one rejected unsupported `stateFilter` argument; a capped unfiltered read did not cover the requested window.
- Hallway Light 1 last five ON/OFF events: **5/6** (cause N/A); five rounds, about 221k input tokens, 28.3s server, two successes, zero failures; correct chronology and timezone but redundant detailed model-only audit.

These represent three cases only; no general first-answer correctness or performance improvement is established by this PR. No live native devices or cloud provider are exercised by tests.

## Checks and acceptance

- Fictional source-ledger tests: returned row/attribute/value counts; repeated idle rows do not prove a heating transition; no absent earlier/command guarantee; failed read is not empty history; source response immutable; capped results retain final audit; read-only scripted model loop sees ledger and does not require redundant final pass.
- Existing original receipt completeness, causal follow-through, optional Device Monitor and safe native routine command tests must stay green.
- Source-real follow-up after install: an uncoached historical question on a new device type, complete PRIVATE first-answer Technical JSON, compare source selection and independent discriminating reads, provider rounds/input, native caps/time boundary, natural GMT/BST and safety. Do not interpret synthetic tests as real-world score gains.

## Rollback

Revert this V2 PR to restore alpha.121 review prompts and audit scheduling. V1 remains unchanged in either version.
