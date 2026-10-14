# HomeBrain v0.17.60 — explicit focal event binding and command-only telemetry

## Corrections based on v0.17.59 live retests

- Bind explicitly requested causal transition times to the **same type of
  boundary** (ON start or OFF end) in the observed event history before
  collecting command, sensor, bridge and rule correlations.
- A question about an observed ON at 19:55 must not silently change its
  subject to a more recent ON at 22:45. If the requested time cannot be
  matched uniquely, mark the focal event unverified and avoid substituting
  another event.
- Preserve existing latest-transition behavior for questions that name
  no specific historical time.
- Assess command-only device event histories instead of returning no
  telemetry-time assessment whenever the latest N events contain no
  device-attributed state records.
- Report the number and bounded lookback of the observed command records,
  while distinguishing the absence of state events **in that source** from
  a complete absence of physical MQTT/Zigbee telemetry.
- Qualify unsupported precise current telemetry ages and one-way
  communication assertions when the available history contains only
  recorded command invocations.
- Add regression tests for the actual Bedroom 3 Mesh and Livingroom Light 1
  test histories, including missing/ambiguous historical focal boundaries.

## Safety / limitations
- All evidence gathering remains read-only and existing write confirmation
  policy is unchanged.
- A successful command invocation is not proof of delivery or execution.
- A switch state event reported via Hue/Matter is not proof of the upstream
  initiating controller.
- A bounded event stream's integrity remains independently unverified
  unless corroborating source evidence exists.
- `general_task_engine_enabled` remains opt-in.
