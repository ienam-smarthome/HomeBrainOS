# Hubitat MCP AI 0.16.128 — Evidence-first automation diagnosis

## Smarter routing and reasoning
- Retain the 0.4-second configuration inventory for `show broken automations` and similar straightforward status requests.
- Send runtime fault/root-cause questions to an investigative model loop with the existing larger, bounded evidence budget. Targets include trigger/event histories, compiled action errors, device references, logs and integration dependencies.
- Route broad questions like `which automations are failing and why?` to the comprehensive read-only System Check, with an optional, user-question-focused AI synthesis (enabled by `automation_diagnostic_ai_analysis_enabled`, default true).
- Keep the separate `comprehensive_audit_ai_analysis_enabled` toggle for generic full-system audit queries.
- The AI synthesis distinguishes confirmed findings from hypotheses and suggests verifiable read-only next steps, rather than treating app enablement as proof of execution.

## Status semantics
- `automation_items[].active` now matches the normalized configuration status, eliminating contradictory `status=active/active=false` records.
- Preserve the upstream explicit activity signal in `explicit_active_signal` and mark `runtime_verified=false`. The status remains *configuration only*, never proof that an automation actually ran.

## Safety and limitations
- No Rule Machine actions, configuration, devices or apps are modified.
- The model cannot magically verify a missing device reference without a read tool exposing the compiled action/target data. Lack of logs or an old timestamp is not alone proof of offline status or failure.
- For broad audits, AI analysis is tool-free after evidence gathering and subject to timeouts; the deterministic findings remain authoritative.
- Issue #725 tracks future deep dependency graph discovery, action-target validation and comprehensive live-hub verification.

## Tests
- Regression tests cover simple inventory vs broad/targeted diagnostic dispatch, contextual question focus and normalized status evidence.
