# v0.18.270 — V3 claim-guided natural incident summaries (fail-closed)

## Live problem

The v0.18.268 Bathroom replay identified input 7895 as a high-quality 5/5 receiver-clock correlation and the model produced a `homebrain-claims.v1` envelope (6 supported claims, 1 rejected), but the user saw an excessively long deterministic digest, generic hypotheses and no headline. A supported witness envelope can verify only typed event claims, **not** the model's surrounding prose. The trace did not expose which specific claim was rejected; guessing would be unsafe.

## Changes

- Introduce `causal_claim_publication.py`, an evidence-limited, concise natural-language renderer. Its facts originate from validated source-timed Journal switch reports, verified later Hubitat brightness commands, and strictly receiver-clock-qualified one-to-one input correlations. The model selects the witness claims; **the publisher never copies unvalidated free-form prose**.
- Eligibility is deliberately strict: two verified targets, independently recovered source-clock ON and OFF reports for both, at least one valid model-cited source-witness ON and OFF for each, an explicit `upstream_cause_unverified` claim, **zero rejected claims**, and original native-history gaps. Otherwise the existing source-first digest is preserved.
- The published summary leads with the strongest explicitly qualified motion-correlated pattern when available, follows with per-light cycle counts and sequencing, and ends with the verified brightness-command ordering and exact remaining issuer evidence gap. It avoids a ten-row repetitive timeline and generic speculative alternative list.
- Updated `causal_claim_pilot.py` to show both ON and OFF source witness IDs for each target and a five-claim minimum publication example. No additional model rounds, MCP reads, or control authorizations.
- Add privacy-safe, allowlisted `v3_claim_reason_*` metrics for rejected claim kinds, `v3_claim_guided_publications`, and `v3_claim_guided_fallback`. This diagnoses future rejections without exposing model drafts, user names, device IDs, timestamps, log text or secrets.

## Boundaries and next acceptance

Valid structured witness claims are **not semantic verification of arbitrary model-authored natural language**. This stage intentionally permits the model's *supported claim selections* to guide an automatically generated readable answer, not the raw model prose. A subsequent separately validated sentence-level semantic gate would be necessary to safely publish truly free model-authored text.

The 6 supported / 1 rejected claims from the earlier live result remain unidentifiable by reason in that old response; v0.18.270 records the safe reason code next time. Live Hubitat and Home Assistant remain unchanged until user installs the add-on.

## Tests

Complete valid-envelope publication; raw invented controller claim suppression; unsupported command origin rejection and legacy fallback; source-vs-collector witness-clock enforcement; partial envelope, missing envelope, absent uncertainty claim, source coverage and renamed-ID metamorphism; paired source witness examples.
