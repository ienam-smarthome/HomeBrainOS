# HomeBrainOS 0.18.81 — Preserve observed excessive-load exceptions in model conclusions

## Live regression (23 October 2026)

Two read-only tests on 0.18.80:

- Whole-hub audit correctly returned `route=comprehensive-system-audit` but saved `comprehensive_audit_ai_analysis_enabled=false` prevented Gemma synthesis. Explicit `ai_analysis.status=disabled_by_configuration` was truthful. The add-on option remains user-controlled and is **not** overridden in this release.
- A general Gemma analysis ran for 63.3 seconds, but falsely said no `LimitExceededException` rows existed for Life360 and Octopus, despite its *own* successful structured `hub_get_logs` receipt containing ERROR rows explicitly naming app 4061. Another receipt identified app 3977. The model also described causation as uniquely proven for app 3977, which overstates what those exception rows can establish.

## Changes

- New `observed_app_exception_guard.py` detects direct Hubitat overload exceptions only from **successful structured current-turn `hub_get_logs` ERROR rows**. It groups duplicate member-device reports by originating app ID.
- At the final `/api/ask` response boundary, correct categorical denials and unsupported app-exclusive causal attribution when the current-turn structured evidence contradicts them. The correction cites the numeric app IDs, identifies the observation's limited scope, and does not assert overall CPU share, common root cause or user-visible hub impact.
- Preserve genuine negative conclusions about another app when its ID does not match the observed exception IDs; never infer an error from performance ranking, summarised text, failed reads, INFO rows or a model-written app label.
- Report `evidence_validation.observed_app_exception_denial_corrected=true` only if the guard actually repaired the response.
- Regression tests replay the anonymised failure shape and protect against false-positive corrections.

## Boundaries

This is a deterministic **factual contradiction guard**, not evidence that Gemma's underlying reasoning improved. The model remains responsible for analytical comparison; observed exceptions are not proof that independently failing apps share a cause.

No Hubitat commands, device/rule changes, default AI-option overrides or paid routing changes. Test 1 must be repeated with AI analysis explicitly enabled and saved to evaluate model quality.
