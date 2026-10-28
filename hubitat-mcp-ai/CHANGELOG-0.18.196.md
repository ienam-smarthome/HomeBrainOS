# HomeBrainOS v0.18.196 — Source-read usefulness and independent evidence utility

## Live regression: v0.18.195 (28 October 2026, 23:29)

Native V2 finished in 32.532 seconds, with 11 successful Hubitat/MCP READ calls and seven model rounds. It correctly identified Google Nest Hub 7934, its three generic WARN entries at 19:55:19 and independently attested calling apps 1679 (Adhan Player) and 4080 (00 Google Calendar Notifier).

The causal investigation still stalled:
- hub_get_app_config(appId=1679) correctly exposed nested app identity and settings-page metadata; the source reported 76 keys, but not settings values or historically executed app behaviour.
- hub_get_source succeeded at the gateway and returned status=success, appId=1679, yet the evidence packet said source_content_available=false. Therefore no code and no source method execution evidence were obtained; this is **not** an implementation inspection.
- The second broad hub_get_logs WARN query enlarged limit from 100 to 200 and returned **exactly the same 71 rows** (43 Bedroom 3 Mesh WARNs and only 3 relevant Nest Hub WARNs) as the earlier scope. No distinct incident window or cursor was requested.
- The mode=devices read took 7.479 seconds and yielded one uninterpretable row; source quality and investigation utility must be explicitly separated from RPC success. A current metrics read reported ~827.84 MB free memory and ~44.9 C; trends contained no points, so they cannot reconstruct CPU at 19:55.
- The completed report correctly did not assign the generic WARN to either app, but spent most of the budget on sources that could not discriminate the cause.

## General structural fixes

1. **Source readiness:** source reads now expose structured distinctions between gateway status, source-text presence and *verified contiguous source coverage*. A successful metadata-only response explicitly states no implementation evidence was examined. The requested independently verified app/driver ID is recorded separately, and any returned ID mismatch or incomplete source span fails closed.
2. **Privacy-safe source declarations:** if the gateway returns a complete, identity-matched source span, V2 can extract bounded, lexical Groovy method declarations using the existing repository parser. It does not project raw code, code comments, secrets or settings values into model evidence, and cannot infer callback execution or causation from method names alone. Incomplete, mismatched or offset source is not described as analysed.
3. **Duplicate broad-log preflight:** when a prior broad past-log query returned fewer rows than its requested limit, a second query with the same mode/level/scope/time filters that changes only to a larger limit is rejected *locally* as a low-discrimination repeat. It is not executed against Hubitat. The model receives guidance to choose a real incident time window, target filter, pattern or pagination cursor. A distinct query remains authorised by the existing read-only guard.
4. **Clear source-backed explanation:** source evidence highlights now say whether actual code was available and identity/coverage verified. A no-code read explicitly rules out implementation claims, but never implies the method is absent.
5. **Read-only invariants:** No write operations, no automatic recovery reads, no device commands, no production Main Ask changes. A model chooses all further operations; the host validates them.

## Regression coverage and limits

Tests exercise the exact metadata-only source response, complete source with private text, conflicting source identity, truncated/offset source, repeated broad queries, distinct narrowed queries, and model-selected read recovery after locally rejected log repetition.

The Hubitat source endpoint may require a different source type, ID, permissions or pagination to return actual code; this release does not claim to correct that backend service or guarantee code exists. It also does not construct a verified runtime call graph or independently validate each natural-language claim. Generic WARN origin and hub-wide CPU impact remain unverified.
