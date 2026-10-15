# HomeBrain v0.17.70 — Skills live acceptance corrections

## Improvements
- Causal fail-closed answer now preserves any exact-target preceding Hubitat command recorded outside the strict direct-command match window. The command is called a **leading candidate**, never proof of delivery or causation.
- Retain intervening OFF/ON reported state changes from the source-typed investigation projection when synthesis repair fails, so the safe answer remains informative rather than discarding evidence.
- Before final synthesis of an investigated offline/telemetry device, complete a missing device-scoped log source (hub_get_logs filtered by the unambiguously resolved device ID), if the live read-only diagnostics gateway is available.
- A broad hub log page no longer substitutes for device-scoped logs. Missing or failed scoped reads still remain unverified.
- Add regression tests based on v0.17.69 Livingroom Light 1 and Bedroom 3 Mesh live test failures, metric registration and architecture map coverage.

## Safety
Read-only diagnostic tools only; user-facing causal confidence stays calibrated to confirmed evidence. No device, Hubitat app, or automation is modified. Historical source gaps and whether the D1's past touch/MQTT input caused the event remain unresolved without external corroboration.

## Validation
Automated CI and subsequent live acceptance tests are separate gates. After updating the add-on, repeat the historical Livingroom Light question and the Bedroom 3 Mesh offline diagnosis, recording source-class coverage and model metrics.
