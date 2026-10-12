# HomeBrain 0.17.8 — Confidence and source-scope validation

The 0.17.7 live test of the Bathroom Light 1 event at 07:53:36 correctly retained the focal event, identified the directly commanding app, and correlated LWR01 motion. However the final response incorrectly ruled out all manual inputs from final command producer identity, rounded 17m 21s to ~17m 22s, and inserted an unrelated “successful logs ... performance analysis” sentence in the certainty table.

## General corrections

- **Separate validation domains:** Performance-statistics, scheduler and diagnostic validators run only for actual performance requests or supported performance-evidence receipts. A normal lighting/device causal investigation that happens to check logs cannot be rewritten into a performance analysis.
- **Differentiate checked from populated sources:** A successful, empty bounded native-log read is a genuine zero-row observation. It is not missing logs or grounds for a performance-data refusal repair. Performance-specific source checks remain enabled for genuine performance investigations.
- **Separate immediate command source from upstream initiator:** App-produced device commands do not prove that a human/manual action was absent upstream. The generic causal confidence guard recalibrates an unsupported “Manual Control: Ruled out” assertion while preserving the verified app command.
- **Correct focal elapsed time:** For one unambiguously requested, observed completed state interval, validate a lone minutes+seconds duration against its recorded integer durationSeconds. Leave broad histories, open intervals and multiple duration mentions untouched.
- **Improve model instructions:** Avoid inferring debug logging is disabled solely because scoped logs are empty; use returned configuration fields where available, and distinguish direct command producer from its possible upstream cause.
- **Read-only:** No home devices, rules, settings, or server safety gates were altered. These changes are agent synthesis/validation contracts.

## Regression suite

New tests cover a successful empty app log without contamination, preserving genuine performance source correction, causal manual-source confidence calibration, focal duration 17m 21s from the 07:53–08:10 event, and leaving broad/multi-event histories unchanged.

## Limits

Matching log absence to a specific debugLogging setting requires the relevant setting to be present in returned data; missing entries alone remain inconclusive. Further live provider/model evaluation is required after installation.
