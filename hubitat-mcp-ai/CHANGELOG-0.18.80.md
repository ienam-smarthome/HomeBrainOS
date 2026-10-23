# HomeBrainOS v0.18.80 — Explain missing AI and prioritise explicit Hubitat load exceptions

## Live regression (23 October 2026)
The updated v0.18.79 comprehensive audit correctly completed in roughly 40.8 seconds with a deterministic read-only evidence report, but the API showed `model:null`, no `optional_ai_advisory` receipt, and no AI interpretation. The report did not disclose whether optional analysis was disabled. Its top-ranked checklist led with offline devices although it also contained direct Hubitat `LimitExceededException` / `generates excessive hub load` error messages for apps 3933 (Octopus), 4061 (member updates) and 3977 (Device Status Report). Three sampled app `pctTotal` measurements exceeded 100.

## Changes
- Respect the existing `comprehensive_audit_ai_analysis_enabled` opt-out. When saved configuration disables optional model synthesis, print **AI reasoning disabled by configuration** near the top instead of silently returning a non-model report.
- Add structured `ai_analysis.status` for comprehensive audits: `disabled_by_configuration`, `completed`, `timed_out`, `unavailable`, or `empty_response`. Never call a model to diagnose its own absence. No-tools synthesis remains optional and the deterministic source report always survives unavailable/failed model rounds.
- In the host-rendered top-priority section, group explicit `LimitExceededException` / `App N generates excessive hub load` log messages by **originating app ID**, not by the device emitting the log or repeated error rows. Rank up to three directly observed app-load exceptions before generic unavailable device statuses. This is an investigation order, not a causal diagnosis or permission to change automation.
- When any sampled `pctTotal` exceeds 100, explicitly flag its **unverified denominator**. Do not interpret such statistics as share of whole-hub CPU or additive percentages.
- Regression tests cover real exception-message patterns, grouping two member-device exceptions into one app, historical vs current evidence caution, opt-out status, success/timeout/empty model reporting, API serialization, non-mutating model call contract and full deterministic fallback.

## Safety and limitations
This release does not infer the source semantics of Hubitat `pctTotal` or resolve the actual excessive-load root causes. It also does not automatically enable a setting deliberately saved as `false`, change model spending, mutate Hubitat or make the free model Claude-equivalent. Users with a saved `comprehensive_audit_ai_analysis_enabled=false` must explicitly switch it to `true` for the actual Gemma-led analysis. If enabled and the model fails, the response will now say so rather than silently omit reasoning.
