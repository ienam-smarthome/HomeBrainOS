# HomeBrainOS 0.18.444 — Phase 2 observed time-series foundation (offline core)

## Purpose

Begin the reusable evidence-calculation layer of the autonomous agent roadmap
without adding bathroom-, device-, room- or question-specific routing logic.

## Implementation

- Introduce `observed_time_series.observed_transition`, a pure deterministic
  operator over source-normalized numeric records with timezone-aware ISO
  timestamps. Supports first/last matching source predicates and first strictly
  later matching destination predicates, with <, <=, >, >=, =, != semantics.
- The response distinguishes an observed elapsed interval from an **unknown
  real physical threshold crossing**, and never asserts historic absence,
  retention, pagination completeness or device identity.
- Reject ambiguous local timestamps, nonnumeric/NaN values, unsupported
  comparisons and invalid thresholds; handle unsorted records and UTC offsets.
- Add twelve offline tests covering strict comparisons, sample interval
  arithmetic, DST, equal timestamps, invalid/missing sources, and non-humidity
  numeric comparisons.

## Limitations and safety

The new module is **not yet invoked by live MCP tool selection or final
answer synthesis**. It receives no independent event-source, device or
pagination receipts. Phase 2 source normalization, structured proof obligations,
coverage verification, integration and source-real held-out benchmarking remain
pending. No model confidence or first-answer gain can be inferred from its
unit tests.

No Hubitat/Home Assistant/router device or automation is modified. No new write
permissions, background jobs, provider billing, new retries, or operational
timeout changes. Phase 1 defaults remain in effect. The add-on version is
incremented to satisfy the repository's required release gate for any runtime
source addition.

## Rollback and acceptance

Mandatory GitHub CI must pass before merge. The v0.18.443 source-real humidity
and held-out history question remain an open live acceptance gate. If any
unrelated release or integrity test fails, do not merge. Roll back to the
previous add-on package if unexpected runtime effects appear.
