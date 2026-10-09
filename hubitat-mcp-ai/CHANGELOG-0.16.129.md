# Hubitat MCP AI 0.16.129 — Evidence-grounded integration and audit answers

## Fixed

- Treat targeted integration/polling failures as investigative requests, not ordinary read questions.
- Warn when a `hub_get_logs` result hits the requested row limit. Recent INFO or 'online' messages do not prove that no earlier failures occurred in the requested lookback.
- Add a deterministic final-synthesis validation/repair gate for overconfident 'no polling failures' and uninterrupted healthy-operation conclusions from saturated logs.
- Keep optional AI audit commentary at a coherent paragraph/line boundary instead of ending midway through a finding.
- When the `sensecap_d1_intentionally_powered_off` option is enabled, explicitly provide that known user configuration to optional audit synthesis so it does not invent an unknown network fault.
- Add regression tests using representative Octopus telemetry and SenseCap diagnostic cases.

## User configuration

If SenseCap D1 is intentionally unplugged, set `sensecap_d1_intentionally_powered_off: true` in the Home Assistant add-on configuration options, then restart the add-on if required. Leave this false when the unit should be reachable. The setting is not globally enabled for others.

## Scope

Read-only MCP and answer-quality changes only. No Hubitat devices, rules or apps changed. Full Rule Machine action-target validation and end-to-end fault dependency tracing remain open under issue #725.
