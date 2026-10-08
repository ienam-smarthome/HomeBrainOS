# Hubitat MCP AI 0.16.116

## Changed

- Respect explicit INFO/DEBUG/TRACE log severity instead of inferring errors from routine explanatory messages containing words such as "failed"; keep WARN/ERROR authoritative and preserve fallback classification for truly unlabelled rows.
- Parse nested MCP Rule Server JSON entry messages from the full raw record before truncation, preventing long metadata from hiding validation errors.
- Show independent alert counts separately from unverified automation *BROKEN* name markers in chat headlines and coverage.
- When the initial 24-hour log response returns its 200-row maximum, perform one bounded older-window read covering 24-to-6 hours before the audit. Show observed historical warnings/errors and disclose when this sample is itself saturated or unavailable. This is not exhaustive archival log coverage.
- Cross-check unmatched top-ranked performance-device IDs against Hubitat's live context if a complete authoritative context resource is available. Incomplete or failed reads do not prove absence.
- Preserve source evidence receipts and all existing Hubitat mutation/confirmation boundaries. No repair is carried out by the diagnostic route.

## Validation

- Adds tests for real-world washing-machine INFO messages, nested JSON errors longer than 500 characters, bounded 24-to-6-hour windows, device ID reconciliation and alert count provenance.
- Full repository and container CI results verified on the pull request prior to merging.
