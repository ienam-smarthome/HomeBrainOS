# Hubitat MCP AI 0.16.57

## Performance synthesis quality

- Performance answer validation now activates whenever the current turn has successful `hub_get_performance_stats` evidence; it no longer requires a log read just to keep a performance-only answer actionable.
- Log-specific causality and one-sided threshold safeguards remain conditional on actual `hub_get_logs` evidence.
- Diagnostic performance answers that omit recommendations now receive bounded, inspection-first `Grounded Next Actions` without inventing device-specific values.
- Configuration/tuning localization is Markdown-table aware: unsafe advice inside a recommendation table keeps the component and impact cells while only the Action cell is replaced.
- The configuration guard now catches broader ungrounded tuning forms including polling/reporting intervals, reporting thresholds, config pushes, exact numeric interval/threshold examples, and exact Rule Machine cadence prescriptions.
- Unsupported mechanism claims such as network timeouts, slow API responses, excessive polling/config pushes, retries, reconnects, or thread blocking are localized as hypotheses unless the current turn actually read relevant code/configuration/settings evidence.
- Explicitly conditional analysis such as `could block execution threads if calls are synchronous` remains allowed.
- No additional Hubitat reads are introduced and performance/log evidence collection is unchanged.

## Live regressions

Coverage includes the 0.16.56 performance-only response that omitted all next actions and the table-form response that mixed measured LG/SenseCap/Halo/Octopus findings with unsupported async/timeout, polling, reporting-threshold, and cadence prescriptions. Release metadata and both repository/add-on README version references are aligned to 0.16.57.