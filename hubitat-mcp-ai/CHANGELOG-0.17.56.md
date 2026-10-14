# HomeBrain v0.17.56 — typed event provenance and diagnostic coverage

## Fixes

- Device-only claim grounding now excludes typed app, automation and integration
  identities found inside returned MCP event data. For example, a
  `command-refresh` event with `producedBy.type=app` for Device Health
  Monitor is evidence of an app-issued refresh, not an additional device that
  must be resolved and independently queried.
- Real device claims still require matching target-device evidence. Untyped
  device resolver targets and expressly typed `device` records continue to
  participate in device grounding. The existing retry/refusal gate remains.
- A deep read-only causal question beginning with Investigate/Diagnose/Explain,\n  and asking why an event happened, is no longer misclassified as a write\n  merely because it describes a historical turn-on or turn-off command.\n- Extend the existing cross-route `device_telemetry` diagnostic plan to
  investigations about telemetry activity, device health and recent device
  logs even when questions don't use the words "offline" or "stale".
- The shared API completion gate can now report that a read of unscoped
  whole-hub logs or a different app's logs is not proof that targeted device
  logs were checked.
- Regression tests reproduce the live Bedroom 3 Mesh (device 7103)
  and Device Health Monitor (app 4072) false refusal and preserve
  legitimate mismatched-device detection.

## Safety and boundaries

No Hubitat device, app, rule or setting is changed. This release does not
claim to prove the physical device responded to refresh/on commands, that
the MQTT status is fresh, or that a causal sensor issued a command.
`general_task_engine_enabled` remains disabled by default.
