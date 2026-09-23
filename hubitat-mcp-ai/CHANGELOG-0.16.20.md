# Hubitat MCP AI 0.16.20

## Compact device inventory drill-down

0.16.19 proved the new host-owned device inventory path live:

```text
191/191 devices returned
identity_cache_hit: 1
tool_calls: 1
local_tool: 5 ms
total: 36 ms
model: null
```

The retrieval path is already fast and complete. 0.16.20 therefore changes
presentation and request parsing only; it does not replace the successful
identity-cache/live-context architecture.

## Compact whole-home summary

A broad request such as:

```text
list devices
```

now returns the total inventory and group counts rather than all 191 names.

Example shape:

```text
191 Hubitat devices across 21 groups.

Groups: Appliances 8 · Apps 3 · Bathroom 6 · ... · Unassigned 55.

Ask for one group to see its device names, for example
list Bathroom devices or list unassigned devices.
```

This keeps the common response practical on mobile while preserving the full
authoritative inventory underneath.

## Scoped inventory drill-down

The same deterministic fast path now recognises structural group requests such
as:

```text
list Bathroom devices
list unassigned devices
list devices in Living Room
show living devices
```

A scoped request returns only the device names in the matched group.

Matching rules are deterministic:

- exact case-insensitive group matches win;
- a unique partial match is accepted;
- multiple partial matches are reported as alternatives rather than guessed;
- an unknown group returns the available group/count summary.

For example, if Bedroom 1, Bedroom 2 and Bedroom 3 all exist,
`list bedroom devices` asks the user to choose one instead of silently
selecting a bedroom.

## Live-state guard

Structural inventory routing must not steal live-state or device-kind queries.

The following remain on the normal live query path rather than the inventory
shortcut:

```text
show active devices
list offline devices
show open devices
list motion devices
show light devices
list low battery devices
```

This matters because the inventory cache is authoritative for identity and room
membership, not current switch/motion/battery/health state.

## Performance contract

Both compact summary and scoped group requests remain host-owned deterministic
reads. On a warm identity cache they are expected to retain the 0.16.19 shape:

```text
model_rounds: 0
remote hub_list_devices pagination: 0
provider timing: absent
one local inventory tool call
```

## Regression coverage

0.16.20 adds coverage for:

- compact whole-home group/count rendering;
- scoped Bathroom, Bedroom 1, Living Room and Unassigned inventory;
- exact and unique partial group matching;
- ambiguous Bedroom matching without guessing;
- unknown-group fallback with available counts;
- zero provider/model calls for scoped inventory;
- no remote device pagination for scoped inventory;
- live-state/device-kind phrases excluded from the inventory fast path;
- parser output for compact versus scoped requests.

A small documentation cleanup also replaces a literal `\n\n` sequence left
in the 0.16.19 architecture section with a real paragraph break.
