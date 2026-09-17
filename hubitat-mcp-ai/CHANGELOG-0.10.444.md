# Hubitat MCP AI 0.10.444

- Reject a trigger-only `Certain Time (and optional date)` capability when it is used as a Required Expression condition.
- Require `Between two times` for Required Expression clock windows and reject unsupported comparator/flat-time fields before confirmation.
- Preserve explicit relative delays from the user request in the ordered Rule Machine action list before any write can be queued.
- Add regressions for the failed Big Lamp app 4205 proposal so the malformed rule cannot create another partial shell.
