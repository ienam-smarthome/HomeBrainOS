# Hubitat MCP AI 0.10.297

## Added

- Added `technical_metrics_presenter.present_request_metrics` as the stable presentation boundary for request metrics in technical details.
- Added compact formatting for counters, millisecond durations, second durations, and final outcomes.
- Added focused tests for formatting, unavailable values, unknown outcomes, and privacy-sensitive dynamic keys.

## Privacy and safety

- Only the fixed request-metric vocabulary is rendered.
- Unknown keys are ignored rather than displayed dynamically.
- Prompt text, device names, session identifiers, tool arguments, and arbitrary labels cannot become technical-detail rows.
- Zero counters and unavailable durations are omitted to keep the panel concise.

## Follow-up

- Wire the presenter into the existing WebUI technical-details rendering seam after this component passes the release gate.
