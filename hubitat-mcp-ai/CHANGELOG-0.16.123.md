# Hubitat MCP AI 0.16.123

## Changed

- The deterministic automation-status response retains established summary and status-list formatting while showing separate totals for installed app instances and Rule Machine entries.
- Automation rows include the exact source ID when available, making it easier to distinguish deleted legacy apps from current records.
- The output now explicitly states that an enabled or unflagged app is not verified healthy: this lightweight status inventory does not inspect runtime logs, device availability, compiled actions, or dependencies.
- A *BROKEN* label alone is presented as an unverified Hubitat name marker rather than definitive evidence of a failing command.
- The existing comprehensive read-only System Check is suggested when the user's concern is runtime failures.

## Safety and scope

- No automatic Hubitat writes, app repairs, rule disabling or deleted-device cleanup.
- This is a focused reporting improvement and **not** the complete compiled-action/dependency investigation described in issue #725.
- Added regression tests for unverified name markers, explicit failure signals, IDs, and inventory coverage; existing report formatting tests are preserved.
