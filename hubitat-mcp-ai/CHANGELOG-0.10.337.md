# Hubitat MCP AI 0.10.337

- Reuse an exact unfiltered `hub_list_devices` response across separate read-only requests for at most two seconds.
- Keep the existing request-local snapshot reuse so multi-step deterministic resolution still records one authoritative inventory read.
- Restrict shared reuse to the canonical empty-argument live-device inventory call; device history and filtered gateway operations always remain uncached.
- Invalidate the shared snapshot immediately before and after every structured mutating tool attempt, including failed writes.
- Guard against a read that began before a write repopulating the cache after invalidation by using a generation check.
- Add regression coverage for TTL expiry, isolated result copies, and write invalidation.