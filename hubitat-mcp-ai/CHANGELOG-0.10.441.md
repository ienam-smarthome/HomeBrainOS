# Hubitat MCP AI 0.10.441

## Required-expression shape preflight

- Validate `addRequiredExpression` and `replaceRequiredExpression` structures before confirmation and again before replay.
- Reject the live-observed flat `startTime`/`stopTime` form for `Between two times`; require `start` and `end` endpoint maps with valid clock/sunrise/sunset types.
- Validate required-expression conditions, boolean operators, clock values, and numeric offsets before Hubitat can create a partial rule shell.
- Report a returned app ID from a failed create as a partially created rule and explicitly instruct the user to pause or delete it.
- Stop preloading the full device inventory for every mutation; targeted device resolution remains mandatory and avoids the live-observed 30-second, 124-device scan.
- Add regressions for the Big Lamp 02:30–06:30 payload, partial appId reporting, and manifest-free mutation routing.
