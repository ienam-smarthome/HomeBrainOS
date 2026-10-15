# HomeBrain v0.17.71 — Evidence-ranked skill conclusions

## Improvements
- Introduces a reusable evidence-to-conclusion layer over the Skills Framework's source-typed hypotheses, rather than adding new literal external-controller phrase repairs.
- When causal model synthesis and its repair cannot be validated, the fail-closed answer gives a clear leading recorded command candidate, the intervening state anomaly, supported alternatives, checked producer configuration/log coverage, and the decisive read-only next check. Command invocation never becomes proof of transport delivery or upstream user action.
- Offline telemetry reports now lead with a calibrated working diagnosis (Hubitat reports offline and observed telemetry is stale or absent in a bounded history), distinguishing MQTT connection flags from actual device-originated packets.
- Device-scoped log results explicitly report zero rows when a successful scoped query returned zero, rather than only stating that logs were queried.
- Adds regression tests replaying the 15 October 2026 v0.17.70 Livingroom Light 1 and Bedroom 3 Mesh responses.

## Safety and limits
- Read-only investigations; no Hubitat automations, settings or devices changed.
- A recorded SenseCap command remains a leading candidate, not proven cause. Historical broker/Hue-side records may no longer be retained.
- Cached lastSeen/dataAgeSeconds disagreement does not independently prove a hardware/network fault. Live user acceptance remains required after updating the add-on.
