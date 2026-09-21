# Hubitat MCP AI 0.14.19

## Fast routine device-control resolution

- Fix a live performance regression where a simple exact device command could
  spend about 24 seconds refreshing `hub_list_devices` before a sub-second
  verified command was dispatched.
- Add a nonblocking local identity lookup that can resolve a unique exact cached
  device target without any Hubitat identity read.
- Keep the existing live `waitFor` command verification; only target resolution
  is skipped when identity is already known.
- Restrict the zero-I/O cached path to exact/semantic-exact matches so stale
  fuzzy candidates never become direct mutations.
- On a cold cache, prefer the complete one-shot `hubitat://context` identity
  snapshot before falling back to the heavier paginated detailed manifest.
- Distinguish local-cache target resolution in evidence/metrics so future slow
  commands make cache hits vs identity refreshes visible.
- Preserve room-wide, all-lights, ambiguous-target, toggle, scheduled-action,
  and safety fallback behaviour.
