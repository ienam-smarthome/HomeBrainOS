# HomeBrainOS 0.18.428 — 30-day external diagnostics and confirmed startup markers

- Extend external Hub Diagnostics history from a 24-hour API limit to selectable **1 hour, 6 hours, 24 hours, 3 days, 7 days, or 30 days** (clamped to configured recorder retention).
- Stream samples from the existing HomeBrain SQLite database and reduce only long-range *display* results. Keep real first/last, minimum/maximum and outage-boundary observations per time bucket, including short memory dips. Never average values into invented readings.
- Request Hubitat's **read-only** `/hub/eventsJson` at most once per five minutes while the recorder is enabled; retain only confirmed `systemStart` events with offset-aware timestamps and their firmware build when supplied.
- Draw labelled amber reboot/startup lines at verified `systemStart` timestamps, and show a list of captured startups with recorded firmware versions. Connectivity failures remain a separate category and do not prove reboot or reboot cause.
- Preserve native five-minute Java/CPU timestamp deduplication, 30-second OS sampling, historical point tooltips, zero/unknown distinctions, existing 30-day SQLite data and all device/automation safety boundaries.
- Reboot marker coverage starts with events returned by Hubitat after collection is enabled; the hub may not retain all older events. A missing marker is not proof of uninterrupted hub uptime.
- Add regression coverage for long-window limits, extrema preservation, missing-sample segment boundaries, true hub event timestamp parsing, deduplication, and UI integration.

The new hub-events read is low frequency (one additional read at most every five minutes). No new Hubitat code, devices, commands, or writes.