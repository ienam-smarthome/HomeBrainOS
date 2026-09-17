# Hubitat MCP AI 0.10.452

- Resolve semantic device-history windows from the authoritative Hubitat location timezone reported by `hub_get_info.timeZone`, instead of the Home Assistant add-on/container timezone.
- Validate the reported IANA timezone with Python `zoneinfo` and cache it for five minutes to avoid adding a hub-info round trip to every repeated calendar-history query.
- Keep fallback behavior explicit when the upstream timezone is unavailable: preserve the supplied runtime timezone and mark the time-window source as `runtime_fallback` rather than silently presenting it as authoritative Hubitat local time.
- Expose `timeZone`, `timeZoneSource`, `startUtcOffset`, and `endUtcOffset` in bounded `timeWindow` evidence so live tests can verify the exact local calendar interpretation without exposing hub IP, coordinates, zip code, or other `hub_get_info` PII.
- Compute the upstream `hoursBack` safety bound in absolute UTC elapsed time as well as local wall time, preventing autumn DST fallback from under-fetching the predecessor-state buffer.
- Preserve exact semantic-window clipping and the 0.10.450 deterministic duration consistency guard; only the timezone authority and DST-safe fetch boundary change.
- Add regression tests covering a UTC container with a Europe/London Hubitat timezone, timezone caching, PII-safe evidence, invalid-timezone fallback, and the Europe/London DST fallback night.
