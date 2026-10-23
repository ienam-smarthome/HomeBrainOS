# HomeBrainOS 0.18.79 — Route comprehensive health, performance and scheduler investigations correctly

## Live regression (23 October 2026)

A v0.18.78 free-model test of a read-only comprehensive Hubitat investigation covered device health, application performance, scheduled jobs and recent error logs. HomeBrain instead used `unified-mcp-agent`, ran multiple individual reads, hit its 90-second deadline, and returned `investigation-timeout` with no actionable synthesis. All observed reads were non-mutating.

## Root cause

`is_cross_domain_hub_audit_request()` required an **automation/rule** domain to use the fast comprehensive audit pathway. The natural-language request had five independent source domains but did not mention automation. `is_comprehensive_system_audit_request()` also failed to match the request's phrasing. Therefore the 0.18.78 model-led comprehensive audit path was never reached.

## Correction

- Recognize a whole-hub, read-only multi-domain investigation when it requests recent logs, scheduled jobs, performance and health/device observations, regardless of whether it says *automation*.
- Continue excluding targeted historical device-transition questions and rule-specific investigations from the broad route.
- Add an explicit mutation guard before any deterministic whole-hub read shortcut so requests containing real write commands continue to the established agent/confirmation pathway.
- Regress against the uploaded real question, adjacent whole-hub phrasings, targeted queries, explicitly mutating requests, AI enabled/disabled routing, and existing comprehensive audit syntax.

## Limits

This fixes the audited route selection, **not** independent inference quality for every free-model question. Comprehensive audits still use deterministic source collection with an optional bounded no-tools AI interpretation and safe fallback. It does not guarantee an AI response on a model timeout, does not change the 90-second general-agent deadline, does not reduce fresh inventory retrieval latency, and does not authorize Hubitat changes.
