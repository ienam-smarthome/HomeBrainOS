# HomeBrain v0.17.59 — provenance-gated causality and bounded telemetry

## Repairs from v0.17.58 live investigations

- Added a common focal-causal claim guard that runs on the model's initial
  answer AND on the one bounded synthesis repair. The guard checks the
  structured event graph's command/external-initiator proof slots before a
  narrative may attribute the initiating logic to an outside automation.
- "No matching Hubitat command found" is treated as a scoped negative
  observation, never as proof that Hubitat issued no command or that a Hue,
  Matter, or other external controller was responsible.
- Downstream event listeners remain observations rather than automatically
  cleared or blamed actors. Nearby FP400 motion remains a signed temporal
  correlation, not verified initiating control.
- Expanded timestamp-driven telemetry answer reconciliation so a bounded,
  truncated Hubitat event list cannot be represented as the physical
  device's complete MQTT/Zigbee history.
- Restates device-attributed events and sampled command calls as bounded
  observations, without claiming an end-to-end response failed merely from
  missing state changes in the returned sample.
- New focused regression tests exercise the exact v0.17.58 living-room
  causal conclusion and Bedroom 3 Mesh contradiction and retain legitimate
  observational and possibility language.

## Safety
- No Hubitat mutation. Rules, devices and existing confirmations are untouched.
- A focal causal proof obligation can remain unresolved even after many MCP
  source reads. In that case the answer must preserve proven observations
  and explicitly withhold unsupported initiator attribution.
- The guard covers known source-proof claim forms, not unconstrained natural
  language. It is not a universal verifier of all possible causal prose.
- `general_task_engine_enabled` is still disabled by default.
