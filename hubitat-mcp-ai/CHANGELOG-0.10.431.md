# 0.10.431

- Coalesce concurrent dashboard/device-manifest refreshes so only one whole-home inventory fetch runs at a time.
- Let an aggregate live-state request such as active rooms await an already-running device-manifest refresh and reuse its completed device list instead of waiting for the MCP lock and issuing a duplicate `hub_list_devices` read.
- Preserve the existing two-second completed-snapshot freshness bound and mutation invalidation generation checks.
- Add regression coverage proving overlapping manifest/live-snapshot requests produce one upstream POST, concurrent refresh callers share one fetch, and a write invalidation prevents stale in-flight state reuse.
