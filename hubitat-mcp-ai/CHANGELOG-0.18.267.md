# v0.18.267 — V3 receiver-clock evidence and historical summary integrity

## Issue
Live Bathroom replay found ten source-clock switch events per target and identical-state collector-reception copies, while input sensor 7895 reported exactly five active and five inactive collector receptions. The old digest reduced these to generic co-occurrences, summed per-device reported connection gaps, and treated bounded receipt samples as full archive counts.

## Architecture
- A pure source-agnostic reception evidence module compares collector-received input rows to collector-received switch rows on the *same collector clock*; it never converts a sensor reception into an original sensor event timestamp.
- Candidate one-to-one association requires a complete, untruncated returned input page, unique matching reception events and source-qualified journal target histories. It does not attest a controller or exclude independent transport delays.
- Source-to-collector lag is measured **only** for the target stream; it is not presumed applicable to the sensor stream. The module also records per-light source-timed stagger, without attributing a common controller.
- The read-only bridge exports this bounded analysis to model synthesis and the existing deterministic fallback.
- Retrieved input row counts and retained receipt sample counts are reported separately. Gap counts are presented per archive query; the same collector gap may be reported more than once, so a sum is not described as distinct outages.
- The legacy digest now leads with the strongest fully paired receiver-clock pattern and qualifies its attribution, quantifies per-light sequencing and recorded setLevel ordering, then retains its historical timeline.

## Evidence boundary
The association is not a statistical p-value, a matched original sensor clock or a verified command origin. Device 7895 is an investigation lead; source-side command history and controller dependency tracing are still required. No automatic topology prefetch, forced hard-round stop, or deletion of collector-only evidence is introduced.

## Regression
Reusable synthetic replay fixtures check stable receipt-clock deltas, staged per-light source times, 170 returned versus 30 retained input rows, repeated per-query collector gap counts without false global outage totals, malformed or incomplete evidence, and identity/label rename invariance.

Publication still uses the previous guarded digest path. Device control and Home Assistant/Hubitat installations remain untouched. Subsequent model-led synthesis must validate prose causality separately.
