# Hubitat MCP AI 0.16.51

## Fixed

- Corrected one-sided Rule Machine threshold analysis in performance diagnostics. `Action: Wait for event ... stays that way for: 0:03:00` log rows are no longer misread as event values with a trailing numeric value of `0`.
- Event-value parsing now accepts only log bodies that start with `Event:` or `Wait Event:` when deciding whether sampled trigger values remained on one side of a threshold.
- This prevents a repeated qualifying sample such as 76-86 W against a `>= 65 W` trigger from being incorrectly described as threshold fluctuation simply because the rule action contains a three-minute timer.

## Tests

- Added the real Rule Machine `Action: Wait for event ... 0:03:00` line to both the performance-causality regression and the `/api/ask` serialization regression.
- The API guard must now remove unsupported `fluctuating slightly` wording when the current-turn trigger/event evidence remains entirely on one qualifying side.