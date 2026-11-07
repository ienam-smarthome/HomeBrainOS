# HomeBrainOS v0.18.457 — Preserve unpaired returned OFF observations

## Changed

The adapter now reads both source `observedEvents` and `boundaryEvents` for state focus and pairing, validates state-change/type/time/reporter fields and deduplicates identical state/time witnesses. Boundary projections describe interval edges and may omit an older unpaired OFF that is still in the raw returned source sample. That row must remain in the command-pairing denominator. Explicitly non-authoritative projected receipts cannot add sample witnesses.

Includes the merged v0.18.456 default-past and focal-log scope corrections. No new runtime module, live reads, model requests, provider/billing or confirmation changes.

## Evidence and validation

The supplied v0.18.455 attachment has six OFF state observations but only five in its interval boundary projection. The previous five-OFF explanation was an adapter/review error, not a changed retained sample. Original private-packet local replay now yields 6 OFF / 2 paired / 4 unmatched returned records; corrected log counts remain 4 total / 1 bounded / 3 unbounded / 0 focal / 0 app-specific focal. No external controller or complete history is established.

Compilation and local source replay passed. Fictional regression covers an unpaired OFF present only in raw observations and deduplication across two projections. All four exact-head CI workflows must pass before merge. Installed v0.18.457 answer acceptance remains unverified; source replay and synthetic tests do not measure general model quality.
