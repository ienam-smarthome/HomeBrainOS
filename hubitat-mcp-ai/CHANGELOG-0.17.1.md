# 0.17.1 — General command-semantic causal investigation

Previous HomeBrain causal attribution queried Hubitat `command-on` or `command-off` and correctly analysed bridge state transitions, but did not inspect `command-setLevel` as a potentially initiating dimmer command. A configured controller can turn a light ON with a positive `setLevel()` call without generating a separate `on()` event.

## Command families and evidence priority
- Add an extensible command semantics module. For devices advertising SwitchLevel, setLevel or compatible level/switch attributes, include scoped `command-setLevel` event history alongside the requested ON/OFF command history. Non-dimmer switches retain the existing two-read fast path.
- Preserve the existing two-concurrent-read budget: switch and explicit ON/OFF command are prefetched together; any additional level history is fetched afterwards. All reads remain numeric-device-ID scoped and read-only.
- Parse bounded numeric `setLevel` arguments (0–100) from structured event values or the command description. Positive levels are eligible for ON transitions; zero is eligible for OFF. Unknown arguments, incompatible levels, and colour/scene/toggle methods with driver-dependent behaviour do not become direct switch-cause proof.
- Only correlate commands within two seconds **preceding** the corresponding state boundary. A command logged after the state change remains a downstream adjustment unless the state event independently names the same producing app and supports a narrowly bounded recording-order inversion.
- Retain the actual command name, argument, timestamp, Hubitat `producedBy`, and command-to-state delay in command-level explanations; no longer mislabel `setLevel(20)` as `on()`.
- Detect multiple compatible commands produced by different app IDs around the same boundary. In such a case do not select a unique initiating controller: show both commands and preserve the external bridge reporting path and other sensor evidence. Same-app on()+setLevel() is not treated as two competing controllers.
- Keep the existing direct command precedence and the 0.17.0 cross-integration adaptive sensor correlation for transitions with no unambiguous compatible Hubitat command.

## Regression benchmarks
- Exact ON timing from a positive dimmer `setLevel(20)` preceding a Hue/Matter switch state, with a Hallway-like fixture. The engine is not keyed to any Hallway device or automation ID.
- Reject level commands after the transition, unknown/unsafe arguments, mismatched off-direction levels, old commands that do not match the focal boundary, and configured-but-unproven third-party colour actions.
- Distinguish multiple command-producing apps from one app issuing on() plus setLevel(); keep known upstream controller source and downstream state-event observers separate.
- End-to-end Hubitat MCP gateway and agent tests for dimmers and non-dimmer switches; no model rounds required for an unambiguous direct command producer.

**Scope:** This release does not inspect external Aqara or Home Assistant automation execution logs. Even a verified command producer does not prove which person, upstream sensor, or automation triggered that producer. Do not infer a 15-second OFF timer's execution from a nearby inactive sensor event alone.

Read-only: no hub settings, devices, rules or automations are changed.