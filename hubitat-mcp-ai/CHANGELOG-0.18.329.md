# v0.18.329 — Stage 9.4: align model causal confidence with independent coverage

## Live investigation that exposed this
On 1 November 2026, app 4012 issued a recorded `off()` command to Hallway Light 1, but no historical sensor event or decision log verified the proposed 15-second inactivity timer expiration. The free Gemma response nevertheless claimed the inactivity timeout was the cause with "High" confidence and declared the investigation complete. In the same API response, all three candidate discriminators had `discriminator_verified=false`, `hypothesis_verdict=unverified`, and `rootCauseVerified=null`.

## Root cause in publication flow
The model publishes a narrative before `process_user_request_result` computes independent hypothesis coverage. The JSON previously returned both without reconciling confidence. Reading configuration, source implementation, and an app-issued command can verify those facts but cannot by itself verify an upstream timer decision.

## Changes
- Introduce a generic final-boundary confidence alignment module, applied after coverage is assembled and before `AgentOutcome` is returned.
- When the independent comparison contract explicitly marks all proposed causal discriminators unverified, soften contradictory "Confidence: High", categorical "Leading Explanation" and "investigation complete" wording. Preserve all original evidence, timeline, and useful source analysis.
- Keep cautious model answers unchanged; avoid adding boilerplate to already calibrated output.
- Leave true verified root-cause outcomes, non-causal questions, source data, evidence coverage, and normal model/tool calls unaffected.
- Tests verify the actual synthetic 4012 false-certainty case, independent coverage proof obligations, idempotence, benign cases, no premature publication, and no app/device hardcoding.

## Safety
- No new Hubitat reads, app configuration changes, devices controls, Cloud calls or autonomous actuation.
- Does not infer missing sensor history, runtime execution or physical state.
- Does not enable the V3 publisher or replace the model's natural answer with an incident template.

## Acceptance
After update, ask the same read-only app 4012 investigation for a recent bounded incident. The final answer must retain the precise command/timeline and explanation while acknowledging that a hypothesized historical sensor timeout is **not verified** unless discriminating source evidence is present. The API's `investigation_coverage` and natural-language conclusion must not contradict one another.
