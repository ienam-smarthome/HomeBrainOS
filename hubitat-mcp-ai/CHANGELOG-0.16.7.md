# Hubitat MCP AI 0.16.7

## Fresh host identity grounding

HomeBrain's structural device identity is now explicitly time-bounded.

Previously, once the detailed device manifest had been populated,
`get_device_identities()` could continue returning it indefinitely even after
its ordinary device-cache TTL had expired. That could leave host-owned semantic
grounding with removed devices, renamed devices, or stale room membership.

0.16.7 adds a dedicated `mcp_identity_cache_seconds` setting, defaulting to
120 seconds.

When structural identity is fresh, HomeBrain keeps the fast zero-I/O path. When
it expires, HomeBrain:

1. refreshes the complete `hubitat://context` bulk snapshot first;
2. uses that current room/capability identity when complete;
3. falls back to a refreshed detailed device manifest only when the bulk context
   is unavailable or incomplete;
4. does not silently promote an expired manifest back to authoritative identity.

When several complete local identity sources exist, the freshest source wins.

The same fresh host world now grounds zero-model routine-control plans as well as
model-interpreted semantic plans. A first control after the identity TTL may pay
for one bounded identity refresh; subsequent controls remain cached.

## Typed multi-device semantic selection

The semantic IR now has a real `selection` target carrying multiple canonical
device names.

For an explicit request such as:

```
turn off Hallway Light 1 and Kitchen Light
```

HomeBrain can bind both full device names in the host world and compile one
deterministic control call:

```json
{
  "device_names": ["Hallway Light 1", "Kitchen Light"],
  "command": "off",
  "device_kind": "auto"
}
```

Explicit multi-device switch commands remain on the zero-model fast path. More
semantic phrasing such as "make Hallway Light 1 and Kitchen Light brighter" can
still use the semantic planner, after which the host independently restores and
validates the complete explicit selection.

Overlapping names use longest-phrase matching, and duplicate canonical labels
are not treated as safely explicit identities.

## Identity-path observability

Adds fixed request metrics for:

- local control identity-cache hits;
- control identity lookups;
- semantic identity-cache hits;
- semantic identity refreshes.

This also removes the previous warning path where the control service emitted
identity metrics that were not registered in the fixed request-metric schema.
