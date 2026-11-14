# HomeBrainOS V2 alpha.91 — temporal causal evidence sufficiency (14 November 2026)

## Purpose

Improve general **model-led** causal reasoning in V2 using the original successful native Hubitat MCP receipts. Preserve OpenRouter free/paid and manual Ollama Cloud paid provider, all current native tools, and independent approval for every home-changing operation. V1 **must remain untouched**.

Source-real first-answer reviews of alpha.90 exposed two recurring failure classes: a historical transition requested without the word "why" did not enter causal review; another investigation correctly reported an unknown initiator but did not inspect available discriminating read-only sources. A separate thermostat answer mixed a historic event with a later temperature and treated a setpoint report preceding its command as a subsequent effect. All device names and timestamps are **test stimuli only**, not production source routing rules.

## Implementation

1. **Broaden causal-intent classification** for requests to investigate, trace, reconstruct or explain state transitions, command issuers or controllers, even without literal "why". Do not trigger on plain current-state reads, measurement lists or commands to change the home. Classification never selects a device, model, tool, cause or command.
2. **Time-ordered evidence prompt** asks the model to compare actual previous-state observations, event timestamps, command issuers and later states. A current measurement cannot establish a historical measurement; a state report preceding a command must not be re-ordered to imply that command caused the report. Event producer is reporter; `triggered[]` applications are event listeners. A state report of `idle` does not by itself prove the preceding state was `heating`.
3. **First source-review pass** now receives a bounded navigation index of the existing ORIGINAL tool receipt scopes. The index exposes only safe request/returned coverage fields; it is not a new receipt or an inference of unobserved commands.
4. If the reviewed **causal** draft **explicitly remains unresolved**, has not selected any new read-only evidence, an actual prior receipt exists and more than 25 seconds remain, allow exactly **one additional model-led opportunity** to pick a useful advertised READ-ONLY tool and arguments. No source is preselected, no automatic API or hub read occurs, and the model can decline further reads. The existing review-tool restriction prevents unsafe writes even if the model proposes them. It does **not** turn a negative result, absent command row or event cap into proof that an action did not occur.
5. The existing final source-to-claim audit remains a **tool-free** optional pass. New guidance checks whether the prior state actually appears in returned rows, whether later measurements are being projected onto historical events, and whether the incident had already recovered or changed after the focal event.
6. If the **optional** follow-through model call times out, reaches the deadline or fails, preserve the preceding source-grounded reviewed draft instead of losing the answer. A model error does not dispatch a write or change providers. Private Technical JSON now records `causal_follow_through_invoked` and `causal_review_read_receipts_added`; neither asserts causation.

This is a **bounded cost-quality tradeoff**: unresolved causal investigations may spend one extra model round and (only if the model chooses it) one or more additional native reads. There is no new fee or API permission, no automatic paid model selection, no instrumented USD cost claim, and no claim that a question is independently verified simply because it passed review.

## Verification and remaining limitations

Synthetic CI tests: new causal question detection, noncausal isolation, timestamp warnings, model-selected read, no-op/model-decline, one-shot checkpoint, source-preserving error fallback and rejection of attempted native writes. Old source-review and final-audit tests are kept isolated so their pre-existing behaviour is still tested.

**CI does not independently test a real Hubitat hub or paid Ollama Cloud.** This does not guarantee the model chooses the missing source or that a source exists. The original observation can still be incomplete; report the exact source window and unresolved cause. No incident-specific patches or static cause rules are added.

## Installed acceptance

On an updated V2 Preview alpha.91 installation, ask new READ-ONLY source-real questions rather than replaying the exact already exposed incidents:

- A recent switch/state transition whose initiator is uncertain; compare state/report versus command/issuer and follow-through source selection.
- A thermostat or valve transition; verify that previous state is directly observed and current temperature is not projected backward.
- A causal question with genuinely sufficient receipts; verify no needless follow-through and no source count inflation.
- A noncausal reported-state query; ensure no new review latency.

For each, save PRIVATE Technical JSON. Compare original successful MCP receipts, actual chronological order, returned lookback, row cap, missing source checks, model rounds, `causal_follow_through_invoked`, `causal_review_read_receipts_added`, latency, token counts, no native writes and approval safety. Evaluate factual grounding, source completeness, causal calibration and usefulness without claiming that missing rows prove absence.

## Future work, intentionally excluded

No new fixed incident routing, no deterministic attribution of causes to a device or app, no bypass of model choice or native approvals, no local Ollama path, no cross-provider fallback, no increase in default cloud-paid mode, no V1 changes. An optional structured causality contract can be explored only after source-real A/B evidence shows a general improvement.
