# v0.18.252 — Historical target-scope integrity

## Why

The unified model-led agent correctly resolved three requested Hubitat devices but queried `hub_list_device_events` without `deviceId`. A hub-wide result with no events was incorrectly presented as proof of no ON/OFF activity on those named devices—even though previously verified device-specific histories contained transitions.

## Architectural changes

- A shared read-only `target_history_scope` contract recognizes target identities only from verified targeted Hubitat device lookups, and distinguishes hub-wide history reads from target-scoped reads.
- Before the original MCP model loop stops, one bounded source-scope completion opportunity prompts the model to choose verified `deviceId` histories with the requested period using its existing safe tools.
- The same target-scope gap appears in the general evidence checkpoint, so an unscoped request cannot be mistaken for source completeness.
- A final API boundary protects every path, including early shortcuts: when required per-target histories remain unqueried, categorical no-activity claims are replaced with a clear coverage limitation.
- Structured investigation coverage now includes `targetHistoryScope` and `sourceScopeComplete=false` when sources remain unqueried. A successful source read does not prove complete historical retention.
- This general contract applies to arbitrary verified subjects (lighting, heating and other recorded devices), with no hardcoded Bathroom IDs or app rules.

## Safety & limitations

No new MCP capabilities, Hubitat writes, background actions, credentials or device mutations. The host never invents missing events or assumes that available history is complete. The model retains choice of authorized read tools. A subsequent regression stage can improve planner quality after source-scope integrity is established.

## Verification

Tests cover unscoped zero-event reads, partial target histories, verified deterministic histories, failed/mutating receipts, ambiguous target identities, shared checkpoint disclosure and unrelated current-state requests. Full CI required before merge.
