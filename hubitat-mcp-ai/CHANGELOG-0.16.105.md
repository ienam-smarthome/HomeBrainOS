# Hubitat MCP AI 0.16.105

## History window and duration intent fidelity

- Carries request-scoped semantic history windows such as `this morning` into `homebrain_device_history` arguments even when the model already supplied the state attribute.
- Keeps explicit caller-provided `time_window` arguments authoritative and does not widen a known-attribute `limit: 1` presentation request.
- Passes the original user objective into final synthesis validation so explicit `how long`, duration, and total-time questions cannot omit an available deterministic temporal total.
- Distinguishes recorded event timestamps from source-integrity uncertainty: timestamps present in returned event rows are direct observations, while unverified history still limits completeness, continuity, and exact physical-history claims.
- Adds regression coverage for semantic-window propagation, explicit-window precedence, omitted-duration repair, and recorded-timestamp wording.
- Retains the 0.16.104 rule that presentation limits do not truncate temporal arithmetic.