# HomeBrainOS 0.18.83 — Whole-hub optional AI evidence calibration and model attribution

## Observed 0.18.82 live test (23 Oct 2026, 22:35 UTC)
- Whole-hub audit collected 204 devices, 160 automations, 266 scheduled jobs and a **saturated 200-of-200 newest-log-row sample**.
- Optional AI call returned a nonempty advisory (`ai_analysis.status=completed`), but the external API returned `model=null` because the separate advisory path did not propagate provider metadata.
- The advisory claimed three named apps absent from a **top-20-only** performance list were unlikely to be significant sources of load; converted no observed exceptions in a saturated log page into strong evidence against any app fault; treated a user-reported unpowered SenseCap D1 as proof that its measured app runtime was explained; and confused Hubitat's excessive-load exception with upstream API rate limiting.
- The deterministic host report itself preserved sample limitations and did not authorize these confident conclusions.

## Changes
- Tighten the optional AI system instruction: top-N absence is not measured low load; capped log silence is not historical exclusion; Hubitat `LimitExceededException` is not API rate limiting; unpowered user-reported hardware does not explain app runtime by itself.
- New `audit_ai_advisory_guard.py` corrects those **specific** unsupported assertions in the generated advisory **only when** the same-turn deterministic report independently establishes top-N performance sampling, log saturation or user-reported unpowered SenseCap.
- Preserve verified host evidence and uncertainty; do not invent current exceptions, infer CPU share, infer any device recovery, or mutate Hubitat.
- Retain provider/model identity from the successful request-local transport record in the comprehensive-audit outcome and response. `ai_analysis.model_verified` is true only with that verified record, otherwise `model` remains null.
- Expose `ai_analysis.evidence_calibration` and `evidence_validation.audit_ai_advisory_calibrated=true` when the guard actually corrected generated advisory text.
- Regression tests replay the observed false AI conclusions and model attribution scenarios; verify no changes for already accurate conclusions.

## Boundaries
The deterministic guard can fix known contradictions, but is **not** a general semantic-proof engine and does not establish Claude-equivalent reasoning. Audit completion still requires live comparison and model-quality validation. No setting toggles, home automation writes, paid-model escalation or background monitoring were added.
