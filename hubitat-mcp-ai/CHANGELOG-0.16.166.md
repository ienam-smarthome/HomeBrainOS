# 0.16.166 — Deterministic Rule Machine app investigations

- Route explicit read-only analyses of a named Rule Machine app ID directly to an authoritative hub_get_app_config read, rather than relying on AI tool discovery.
- Resolve only exact sensor labels from the fetched configuration against cached Hubitat identities; read matched sensors by exact numeric device ID, then verify linked parent IDs using native parentDeviceId metadata.
- Report healthStatus, hapStatus and last-reported motion/illuminance separately. A currently offline parent means dependent sensor values have unverified freshness, not that they were necessarily offline at historical execution time.
- Treat an inaccessible app configuration or parent device as PARTIAL evidence rather than claiming a verified rule cause.
- Distinguish mode triggers, IF conditions and required expression configuration; no historical evaluation is inferred from the current editor page.
- Explain that rule conditions can potentially evaluate retained Hubitat values when a separate trigger fires, while avoiding claims that a particular historical action definitely used stale states.
- Keep read counts bounded to four configured sensor identities and four parent IDs; no device or app writes and no model rounds on this narrow explicit app-ID route.
- Regression tests cover verified FP2 parent 7334 and child IDs, unavailable app configurations and parent-health failure.

Other questions continue to use existing AI/general causal routes. This work does not change Rule Machine app 3602 or any device.