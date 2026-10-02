# Hubitat MCP AI 0.16.90

## Scheduled control routing safety

- Prevents the legacy routine-control fast path from executing future-timed ON/OFF/toggle requests immediately.
- A valid clock schedule such as `turn on Block Media-Google-TV-Streamer at 10pm` now bypasses immediate control and remains available to the existing deterministic `RuleAuthoringService` schedule grammar.
- Future/recurring qualifiers such as tomorrow, tonight, daily/every-day, weekday/weekend, day-of-week clauses, and relative/duration wording are also excluded from the immediate fast path so they cannot be swallowed into a device name and executed as `timing=now`.
- Shared clock parsing is used to distinguish a real schedule from established brightness wording; `set Bedroom 1 Light at 50%` remains an immediate level command.
- Immediate commands with no temporal qualifier retain the same deterministic fast path and verification behavior.
- No change to 0.16.89 Internet-group semantics: `switch=on` still means Internet allowed and `switch=off` still means Internet blocked for devices in the authoritative `Internet` room/group, while underlying Hubitat commands remain unchanged.

## Regression coverage

- Immediate switch control still fast-parses.
- Immediate `at 50%` brightness remains a level control rather than a clock schedule.
- Absolute clock, tomorrow/tonight, relative-delay, duration, recurrence, day-of-week, and toggle scheduling forms do not compile as immediate controls.
- `turn on Block Media-Google-TV-Streamer at 10pm` is rejected by the immediate parser and accepted by `RuleAuthoringService`, proving the intended handoff.