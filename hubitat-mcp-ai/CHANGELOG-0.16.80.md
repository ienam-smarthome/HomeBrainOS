# Hubitat MCP AI 0.16.80

## Summary

0.16.80 keeps the accepted 0.16.78-0.16.79 broad-performance architecture unchanged and fixes the remaining timing-label semantics exposed by the 0.16.79 live proof.

## Changes

- Host-derived log timing rows now carry an explicit `timingKind`:
  - `regular_cadence`
  - `irregular_intervals`
  - `observed_gap`
- `regularCadence` remains authoritative for repeated interval series.
- Stable repeated intervals may be described as cadence.
- Irregular repeated intervals are described as an observed median/range and explicitly state that no regular cadence was established.
- Two-point timing evidence remains a single observed gap and cannot be promoted into recurring cadence.
- If a mixed timing section is labelled `Observed Cadence`, the deterministic log guard changes it to the neutral `Observed Timing` heading.
- Existing same-second cluster, WARN/ERROR preservation, timing arithmetic, evidence-first synthesis, and repair-observability contracts remain unchanged.

## Exact live regression

The 0.16.79 live response contained correct host facts but grouped irregular series under `Observed Cadence`:

- Halo3000x ActivePower: regular cadence, median 9.995 s, approximate cadence 10 s.
- Linptech Kitchen motion: irregular intervals, median 2.048 s, observed range 1.01-9.61 s.
- Hallway FP300 illuminance: irregular intervals, median 5.736 s, observed range 3.934-14.676 s.

0.16.80 makes those categories explicit and fail-closed in final presentation.

## Architecture

No new Hubitat reads, no new provider/model rounds, and no change to the host-planned broad-performance source set. The normal broad performance + recommendation path remains three Hubitat reads followed by one evidence-first synthesis round.