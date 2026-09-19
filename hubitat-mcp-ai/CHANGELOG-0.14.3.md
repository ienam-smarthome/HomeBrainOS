# Hubitat MCP AI 0.14.3

## System Check live-result polish

- Separate long-term stale telemetry from ordinary check-in delays. The default
  long-term threshold is seven days and is configurable with
  `health_check_long_stale_hours`.
- Require newly stale periodic devices to remain stale across two audit snapshots
  before raising an individual warning. Correlated and authoritative offline
  findings remain separate.
- Normalize Google TV/FireTV ADB shell timeout logs into one readable,
  occurrence-counted finding.
- Preserve bounded Hubitat status evidence and reported reasons for broken,
  paused, and unknown automation findings.
- Version the persisted issue snapshot. The first audit after an incompatible
  fingerprint change resets the comparison baseline instead of manufacturing
  new and resolved findings.
- Show long-term stale and awaiting-confirmation counts in the WebUI activity
  summary.

## Optional Pushover morning delivery

- Add an optional direct Pushover notification after each scheduled morning
  System Check.
- Include subsystem totals and the top actionable findings in a message bounded
  to Pushover's message limit.
- Keep manual checks notification-free.
- Record notification failures independently so a delivery problem cannot hide
  or invalidate a completed health audit.
- Add `pushover_enabled`, `pushover_app_token`, `pushover_user_key`, and optional
  `pushover_device` add-on settings. Credentials remain user-supplied secrets and
  are never stored in the repository.
