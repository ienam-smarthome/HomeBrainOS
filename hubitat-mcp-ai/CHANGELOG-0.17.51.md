# HomeBrain 0.17.51 — System audit acquisition evidence and offline-state contradictions

## Live issue

The 0.17.50 comprehensive audit read 214 devices through five fresh projected MCP gateway pages; 20,731 ms of its 22,590 ms System Check was spent fetching those pages, versus 118 ms local classification. A different scoped log row reported that Hubitat's internal `/logs/json` GET lasted 8,479 ms and exceeded an 8,000 ms relay budget. That log is evidence of a slow historical request, **not proof that this five-page device scan was itself blocked by /logs/json**.

Four device IDs carried explicit `healthStatus=offline`. Tuya Remote (bedroom 3) ID 3483 also showed a reported activity timestamp 10 seconds before the snapshot. This may indicate an outdated health flag or a device-side event that did not prove reachability. It must not be promoted to an independently verified online condition.

## Read-only improvements

1. **Per-page acquisition timing:** Record bounded end-to-end MCP wall-clock milliseconds for each fresh projected `hub_list_devices` offset, including first page, slowest page, request-concurrency context and fallback diagnostics. The next audit can identify whether slowness is concentrated on a specific page or shared across pages without guessing hub CPU or network causality.
2. **No extra MCP work:** Keep the existing five-page/verified-total pagination contract, semaphore and device-state freshness requirements. Do not increase concurrency, replace fresh data with a stale cache, retry an expensive operation just for metrics, or assume a successful partial page is full coverage.
3. **Offline/recent-activity evidence conflict:** Keep explicit offline warnings and source IDs intact; for a trustworthy activity time within five minutes of the audit snapshot, add a neutral conflict marker and short explanation to the report. A timestamp does not establish command reachability. Ignore apparently future activity timestamps for this conflict.
4. **Source-limited findings:** Preserve already-present guards for the saturated 200-row log window, ambiguous timestamps, top-20 performance samples, and intentionally unpowered SenseCap D1.

## Validation

Tests cover a five-page presentation, 10-second offline/last-activity discrepancy, stale and future timestamps, complete two-page projected gateway with no extra calls, and failed page fallback. Local in-memory simulations only; no live Hubitat commands or settings writes.

Next: run a fresh 0.17.51 system audit, compare per-page wall times, examine why any page is slow, and raise an upstream MCP Rule Server issue with the exact measured offset/timing if the backend remains the bottleneck. This release cannot itself make the 20.7-second remote read faster; it makes its cost diagnosable without compromising accuracy.
