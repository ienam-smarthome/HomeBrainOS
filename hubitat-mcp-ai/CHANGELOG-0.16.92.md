# Hubitat MCP AI 0.16.92

## Scheduled Internet control handoff

- Fixes the 0.16.91 live regression where `block Google-TV-Streamer after 1 min` was captured by the immediate Internet parser and resolved as a device literally named `Google-TV-Streamer after 1 min`.
- The immediate Internet path now reuses the general future/recurring timing guard instead of maintaining a narrower duplicate relative-delay regex.
- `after N minutes|hours`, `in N minutes|hours`, `N minutes|hours later`, absolute-clock schedules, and recurring Internet controls bypass immediate device resolution and remain available to deterministic RuleAuthoringService scheduling.
- Bare immediate Internet controls such as `block Google-TV-Streamer` retain the existing deterministic fast path.
- The 0.16.91 relative one-time scheduler remains unchanged: the requested delay is converted to a dated Certain Time trigger and is not duplicated as a Rule Machine Delay action.

## Regression coverage

- Scheduled Internet prompts using `after`, `in`, `later`, absolute clock, and recurring wording must return `None` from the immediate Internet parser.
- Immediate `block X` still resolves to `blockInternet`.
- The exact live phrase `block Google-TV-Streamer after 1 min` must hand off to RuleAuthoringService with target `Google-TV-Streamer`, not a target containing the timing suffix.
