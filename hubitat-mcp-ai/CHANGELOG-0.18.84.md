# HomeBrainOS 0.18.84 — Optional audit model attribution and cautious interpretation

## Replayed live report, 23 Oct 2026 (v0.18.83)
- Deterministic whole-hub audit inspected 204 devices, 160 automations and 263 scheduler entries, and requested an optional AI interpretation. `ai_analysis.status=completed` but `model_verified=false`, `model=null`; the request was not run inside the ordinary agent's request-observation metrics lifecycle, so the transport's successful provider record had no active request-local destination.
- AI described Bedroom 3 Mesh (7103) and Tuya Remote (3483) as reported offline (grounded), but then asserted that **any** dependent automation would fail despite no verified execution path or observed failed action.
- AI inferred possible executing **ghost jobs** from scheduler-key app-ID candidates matching disabled apps 3892 and 3951, even though the host reported zero explicit job owner fields and no callback execution proof.
- AI stated high `pctBusy` raises risk of hub sluggishness or `LimitExceededException`, though the percentage alone does not establish CPU contention, exception causation or future overload.

## Fix
- For optional no-tools audit model rounds outside `UnifiedMCPAgent.ask()`, start a **scoped RequestMetrics context** only if no request metrics identity exists. Allow the current ChatTransport implementation to record the actual successful model and provider; read the receipt after the response and reset the scoped context in `finally`, including error/timeout. Preserve existing scoped context without nesting or overriding it.
- Tighten the optional AI system instruction to distinguish offline status from proven automation execution failure; scheduler key candidates from verified disabled-app job execution; and measured `pctBusy` from proven hub-wide overload.
- Extend source-conditional advisory calibration to replace specific unqualified claims of failed automations, executing ghost jobs and causal effects of `pctBusy`. No actual current fault, callback owner or CPU rate is fabricated.
- Add regression tests reproducing these three AI claims and verifying scoped provider model capture and reset semantics.

No modifications to Hubitat, devices, automations, saved add-on options or paid routing. This release is a guard and instrumentation improvement, not a certification that independent reasoning now matches Claude.
