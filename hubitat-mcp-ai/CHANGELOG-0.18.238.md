# v0.18.238 — model-authored explanations for independently verified event histories

## Reproduced issue

On 30 October, a Bathroom investigation successfully read the room and three light-event histories (five MCP reads, no transport errors), then returned nine repetitive source-command counts instead of explaining the switch/level chronology. Model planning finished normally, but its output was rejected by the legacy claim-ID publication contract. Because the scope contained several independently verified room members rather than one focus device, the specialised dated-incident synthesis was not eligible.

## Architecture change

- Normalize historical device events from already authorized, scoped MCP reads into a compact source-attested case packet with the device name, event attribute/value, precise timestamp, producer and read ID. A room's devices are accepted only from returned room membership, not model-invented identity.
- For event-rich history investigations, allow a separate no-tools model synthesis to answer the original question and explain the timeline, using exact event citations. Avoid injecting command-count catalogs into planning.
- Independently check model-supplied event read/device/attribute/timestamp anchors, numeric details and overt unsupported causal certainty; reject forged references. Model interpretation is explicitly not proof of physical causation.
- When a narrative fails verification, preserve a chronological, source-backed command/state trace instead of replacing it with a count catalog.
- Distinguish model-authored narrative publication from the legacy claim-catalog diagnostics.

## Boundaries

- No new MCP permissions, no writes, no modification to production Main Ask. Native V2 remains experimental.
- Source-reported device states are not independent physical observations; historical room membership is current-source membership and is not proof of past assignment.
- A brightness command does not prove a sensor initiated the light. Inspect the actual motion/occupancy history and controller decision logs before ranking that cause.
- A model may describe plausible mechanisms but its arbitrary English semantic entailment is **not independently established** by source citations alone.

## Validation

Synthetic replay mirrors the 07:12–07:15 Bathroom two-light state/brightness sequence with room discovery and Shower Light history. Negative tests reject fabricated device references, numeric claims, unverified causal certainty and missing event anchors. Full CI, add-on validation and smoke tests are required before a merge; fixture passing does not establish live root-cause accuracy.
