# Hubitat MCP AI 0.16.55

## Recommendation identity preservation

The 0.16.54 live retest confirmed that configuration-dependent tuning advice is now blocked when the relevant settings were not read, but the safe replacement flattened different recommendations into identical generic bullets.

0.16.55 keeps the original recommendation heading when localizing an ungrounded configuration edit. For example, `Dampen Kitchen Sensor` and `Adjust Energy Reporting` remain distinct in the final answer while the unsafe numeric tuning is replaced with inspection-first guidance.

The replacement text is also scoped to the setting family:

- Rule/automation edits retain the recommendation label and ask for the cited rule/app configuration before exact trigger, threshold, debounce, hysteresis, gap, or duration changes.
- Sensor tuning retains the recommendation label and asks for device settings before exact blind-time or occupancy-timeout changes.
- Polling/reporting tuning retains the recommendation label and asks for integration/device settings before exact interval/frequency changes.

No Hubitat calls, performance evidence rules, threshold compaction, or causality thresholds change in this release.
