# 0.18.4 — Respect explicit Groovy source inspection requests

- Both named-app status and current-lockout shortcuts no longer answer a compound Groovy source, source-code, defaultValue or `state.motionLockout` investigation with only the persisted duration. Such questions proceed to the normal investigative tool-planning route.
- Plain current app-status and lockout-duration/setting questions continue to benefit from the read-only deterministic single-MCP-call shortcut.
- Regression tests preserve both behaviours and ensure no source question silently resolves as a settings-only shortcut.
- **Evidence limitation:** This release does not establish that the upstream MCP server supports reading the installed Groovy application's source. HomeBrain must state source unavailable rather than fabricating methods, stored-state semantics or initialization effects if the underlying source is inaccessible.
- No Hubitat writes or paid-routing/budget changes.
