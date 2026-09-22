# Hubitat MCP AI 0.16.1

## Preserve semantic room capabilities in large homes

A live 0.16.0 request to increase Hallway brightness returned:

> I couldn't find any brightness-controllable devices in the hallway.

No Hubitat read or write tools were called. The semantic planner had received a
capability world, but that world was incomplete.

### Root cause

0.16.0 bounded semantic context by:

1. sorting all capability-bearing devices by room/name;
2. keeping only the first 64 device rows;
3. including a room summary only when at least one of that room's device rows
   survived the cutoff.

In a large installation this allowed later-sorting rooms to disappear from the
planner's world entirely. With roughly 190 device records, Hallway could therefore
look as if it had no brightness capability even when real dimmable lights existed.

The model behaved consistently with the incomplete context; the world projection
was wrong.

### Fix

- Room-level semantic summaries are now built from the complete identity snapshot.
- Every known room retains its aggregated semantic abilities even when none of its
  detailed device rows fit in the bounded context.
- Room summaries expose:
  - canonical room name
  - semantic abilities
  - total capability-bearing device count
  - whether included per-device details are complete
- Per-device detail remains bounded, but is now prioritized by the current user
  request. A request mentioning Hallway moves Hallway device details ahead of
  unrelated devices.
- Context rendering trims per-device detail before room capability summaries.
- If context must be reduced further, HomeBrain emits valid compact JSON rather
  than slicing a JSON string mid-document.

### Architecture

This keeps the 0.16 capability-world principle intact:

- room/device identity and abilities may guide semantic planning;
- current state is still not inferred from cached identity metadata;
- device IDs and raw Hubitat commands remain hidden from the semantic planner;
- live reads and writes remain deterministic after planning.

### Regression coverage

Adds large-home tests with more than 120 capability-bearing devices to prove:

- a room beyond the 64-device detail cutoff still appears with its abilities;
- a referenced room's device details are prioritized into the bounded context;
- aggressive context trimming retains room-level abilities;
- rendered semantic context remains valid bounded JSON.
