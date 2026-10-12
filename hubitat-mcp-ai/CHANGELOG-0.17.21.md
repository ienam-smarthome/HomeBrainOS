# HomeBrain 0.17.21 — Verified windowed MCP historical retrieval

- Reviewed current upstream `kingpanther13/Hubitat-local-MCP-server`: `hub_list_device_events` supports `deviceId`, `appId`, `since`, `until`, `attribute`, and `limit`. Its device window filters apply to the native `/device/eventsJson/<id>` result, not to an archival store.
- When local historical OFF sensor reads start after the requested boundary, HomeBrain now performs up to two precise, read-only, room-local sensor event windows (five minutes before to two minutes after).
- Validates the installed MCP server's echoed `sinceMode`, `sinceTimestamp`, and `untilTimestamp` before accepting records, and checks each returned event falls within the intended window and attribute.
- Verified older event rows feed the existing sensor correlation and timer feasibility engine; they are not classified as causal command ownership.
- If no older rows remain or the installed server lacks verified window support, HomeBrain retains an explicit source-coverage gap and avoids unrelated cross-room expansion. It never fabricates missing history.
- Adds limited request metrics and exposes focal window retrieval status in the causal evidence plan.
- Existing 0.17.20 provenance, bounded command history, and one-round finalization safeguards remain in place.
- Read-only: no Hubitat setting, automation or device is changed.

**Source limitation:** time bounds filter the Hubitat native retained event store; they are not pagination across purged history. Future durable long-term evidence storage is a separate, opt-in feature requiring retention limits and a storage destination.
