# Hubitat MCP AI 0.16.46

## Recognize direct Rule Machine/App execution provenance

The 0.16.45 Microwave live test exposed a correctness gap. Native logs showed:

- Microwave Door contact closed;
- Appliance: Microwave ON/OFF triggered from the door change;
- the app logged `Action: On: Microwave (MQTT)`;
- Microwave (MQTT) reported ON about 90 ms later.

HomeBrain still called that latest run unresolved because native causal parsing only
recognized device-command log phrases such as `turn on command` or
`Command called: on()`.

0.16.46 closes that gap.

### What changed

- native causal parsing now recognizes app/rule log rows of the form
  `Action: On: <subject>` and `Action: Off: <subject>`;
- a direct app action aligned to the requested subject boundary is recorded as
  `app-execution` provenance rather than configuration evidence;
- same-app `Triggered:` and `Event:` rows immediately before the action are
  retained as a bounded trigger chain;
- app execution is sufficient for deterministic causal finalization when the ON
  action is aligned to the subject ON boundary;
- app actions are not paired with arbitrary nearby physical-button logs;
- adds `causal_native_app_execution_provenance`;
- Hallway topology adds `Hallway Sensor P1` as an alias for configured
  `Hallway Aqara P1` in both trigger and derived-source definitions.

### Expected Microwave result

For the observed 19:51:24 run, HomeBrain should now say that
`Appliance: Microwave ON/OFF` issued ON for `Microwave (MQTT)` immediately
before the device reported ON, and may include the same-app Microwave Door
`Event:` / `Triggered:` chain.

That path should finalize without model synthesis once the native log evidence is
collected.

### Causal boundary

A direct app `Action: On` log is execution provenance for the app issuing the
device action. It does not by itself identify a person, and unrelated nearby
physical controls are not promoted into the chain.
