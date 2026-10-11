# 0.16.163 — Lighting rule decision context

- Preserve the fast, authoritative ON-command producer attribution and switch-boundary timing.
- For proven **lighting automation** ON commands, perform bounded read-only follow-ups for that producer's current app configuration and its event-time app log entries. Use the producer's numeric app ID rather than guessing a rule from a device name.
- Distinguish timestamp-aligned *app execution logs* from the *current rule configuration*. Rule configuration alone is never evidence that a condition was true at the command time.
- Where current rule configuration explicitly names a sensor present in authoritative device identity, inspect the relevant room's detailed device states and report current offline/connecting sensor or parent-bridge status with a historical-freshness caveat.
- No hardcoded FP2 device IDs or rule IDs. Current health cannot establish what a sensor reported at an earlier event time.
- No additional follow-up for unrelated device categories, button rules, OFF requests, or cases without direct command-producer evidence; preserve the low-latency fast path.
- Add regression coverage for log timezone windows, inferred sensor-health limits, absent app/log access, zero model rounds, and command-producer authority.

This is strictly **read-only**. The add-on never changes a rule or device. Live rule-log availability and current app-configuration access depend on the installed Hubitat MCP Rule Server and retention/settings.
