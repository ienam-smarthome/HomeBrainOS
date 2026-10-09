# HomeBrainOS 0.16.132 — Optimisation evidence and coverage

## Improvements
- Broad whole-hub optimisation answers now disclose that a top-20 performance ranking is not an exhaustive inventory, and that shared scheduled-job timestamps do not establish CPU contention or a benefit from staggering.
- If the recent 30-minute log read reaches its 100-row cap, the final report explicitly warns that earlier events in the requested window may be absent from the sample.
- Host-derived same-second log clusters are reported as observed clusters only, with a suggestion to verify verbose DEBUG reporting before inferring avoidable work.
- Explicitly distinguish the current performance scan from a complete inspection of Rule Machine action code, device/app configuration and automation dependencies.
- Expanded final-answer repair catches additional wordings that wrongly infer persistent MCP Rule Server dependencies on deleted apps 2597/2954 from failed app-config queries. The correction directs attention to caller/request provenance instead of recommending deleting nonexistent entries.
- Regression tests cover the actual v0.16.131 output's limited source coverage and problematic stale-app recommendations.

## Safety
Read-only. No device, app, schedule or rule settings are changed. True per-job workload grouping, dependency validation and measured benefit estimates remain tracked in issue #733.
