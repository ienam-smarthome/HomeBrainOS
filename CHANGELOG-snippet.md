## v1.0.1-alpha - Event Diagnostics

- Added `/api/event-diagnostics` with event stream health, last 20 events, UI relevance counts, SSE payload counts, and stale-event warning.
- Added compact event diagnostics to `/api/status`.
- Tracks ignored noisy events separately from UI-relevant events.

## v1.0.0-alpha - UI Live Push + Event Filtering

- Browser now applies summary-pills from the event stream immediately.
- Dashboard pushes only UI-relevant event changes and ignores noisy RSSI/voltage/lux/display spam.
- Added SSE heartbeat/fallback behaviour and live status indicator.
