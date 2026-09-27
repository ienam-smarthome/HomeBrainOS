# Hubitat MCP AI 0.16.54

## Configuration-grounded performance recommendations

- Close the 0.16.53 live wording gap where an answer could still prescribe `Edit ... include a duration` or a wider hysteresis gap without reading the cited Rule Machine configuration.
- Treat exact debounce, hysteresis, threshold, duration, trigger-gap, blind-time, occupancy-timeout, polling-interval, and reporting-interval changes as configuration-dependent recommendations.
- When the current turn has not read the relevant configuration, replace those exact edits with an inspection-first recommendation instead of inventing a setting or numeric value.
- Preserve cautious, non-prescriptive wording such as inspecting whether a component exposes suitable debounce/hysteresis controls.

## Auditable threshold evidence

- Keep `thresholdSamples.values` bounded for technical output, but add full-sample `minObserved` and `maxObserved` values.
- Add `qualifyingCount` and `nonQualifyingCount` so `allQualifying: false` is explainable even when a crossing falls outside the first 12 displayed values.
- Continue calculating threshold qualification across the complete returned log result; the additional fields are evidence presentation only and do not add Hubitat calls.

## Regression coverage

- Reproduce the exact 0.16.53 TV-rule, Linptech blind-time, and energy-reporting recommendations and verify that exact configuration changes are blocked without a configuration read.
- Verify that an explicit configuration receipt permits specific tuning recommendations.
- Verify that a crossing outside the bounded visible value list remains auditable through min/max and qualifying/non-qualifying counts.
