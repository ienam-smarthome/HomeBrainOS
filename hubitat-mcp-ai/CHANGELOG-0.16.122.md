# Hubitat MCP AI 0.16.122

## Changed

- The comprehensive read-only System Check now prefers a fresh, lean Hubitat MCP detailed device projection containing ID/name/label/room, capabilities, state attributes and lastActivity; command metadata is not required for health diagnostics.
- The lean audit request is separate from the shared command-capable device manifest cache. It cannot poison command capability data or promote cached identities to live readings.
- For the consolidated device-list gateway, independently numbered pages are fetched through bounded concurrency only when a trustworthy total, page size and advancing offsets are supplied. Check every returned page's shape, identity uniqueness, final count and snapshot invalidation.
- If source metadata is missing, follow the server's explicit advancing pagination cursor serially. Rejected projections, malformed pages, duplicated identities or inconsistent totals trigger a full refreshed detailed-manifest fallback instead of accepting partial evidence.
- Measure and display separate durations for device acquisition and local health classification, retaining the overall inventory stage and source/projection diagnostic provenance. Transport acquisition time includes MCP processing and decoding; it is not asserted to be pure network latency.
- All existing read-only and Hubitat mutation-confirmation safeguards remain unchanged.

## Validation

- Regression tests cover bounded concurrent pagination, projected state completeness, duplicate-ID fallback, serial cursor fallback, shared manifest cache isolation and end-to-end System Check timing/provenance.
- Release CI must pass, including Python tests, metadata and add-on smoke validation, before merging.
