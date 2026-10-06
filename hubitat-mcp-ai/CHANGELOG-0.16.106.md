# Hubitat MCP AI 0.16.106

## Recorded-event wording fidelity

- Fixes a synthesis-validator gap where a model could list timestamps directly observed in returned device-event rows and then call them estimates using the deictic wording `These are estimates based on recorded events`.
- Preserves recorded event timestamps as direct observations while keeping source-integrity uncertainty attached to completeness and continuity.
- Keeps derived duration totals eligible for estimate wording when the device-event stream is unverified.
- Adds regression coverage for the exact live Bathroom Light 1 wording and for the valid estimated-duration case.
- Retains the 0.16.105 semantic-window and duration-intent fixes and the 0.16.104 full-page temporal arithmetic behavior.