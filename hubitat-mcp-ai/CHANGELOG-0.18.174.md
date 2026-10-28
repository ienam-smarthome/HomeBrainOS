# HomeBrainOS v0.18.174 — filtered coverage proof aligned with full inventory

## Reproduced live fallback

On 28 October 2026 at 10:22 UTC, the V2 read of Livingroom Light 2
(#7828) reported switch=off, level=30 with no missing attributes.
It took 22.401 seconds. The live filtered identity lookup was dispatched
and its host-allowlisted READ contract accepted, but was rejected as
`identity_lookup=filtered_coverage_unverified` before the fast device
status read. The subsequent full identity inventory took 21.976 seconds,
while hub_get_device took only 260 ms.

## Contract reconciliation

The complete Hubitat identity auditor already accepts a one-page result
when either:
- the page supplies an exact count in `total` or `totalDevices`; or
- it explicitly supplies `hasMore=false` as a terminal-page marker,
  even if no numeric total is supplied.

The V2 filtered lookup was unnecessarily stricter: it required an
integer `total` and `hasMore=false`, and ignored `totalDevices`.

The corrected scoped proof requires:
- exactly one returned device with a decimal ID and exact friendly label;
- a page object with either a matching nonnegative `total` /
  `totalDevices`, or an explicit `hasMore=false` terminal marker;
- no `hasMore=true` indication and no advancing `nextOffset`;
- rejection of malformed total values (including booleans), wrong totals,
  non-boolean pagination flags, missing coverage markers, duplicate
  entries, unknown labels or a wrong device ID;
- an independently ID-attested, fresh READ response from hub_get_device.

The metadata only establishes uniqueness within the *reported filtered
result*. V2 explicitly marks home_inventory_complete=false for scoped
results and cannot use them as whole-home inventory completeness proof.
The existing full-inventory fallback and the read-only restrictions
remain unchanged.

## Diagnostics and acceptance

`targeted_status.filtered_coverage` now reports only bounded structural
metadata: returned row count, presence/normalised value of total or
totalDevices, hasMore status, terminal cursor and coverage_confirmed.
No raw MCP text, device IDs, device labels, or secrets are copied
into this structural diagnostic.

Automated tests cover terminal marker without total, the totalDevices
alias, complete totals without hasMore, malformed/inconsistent values,
and the V2 HTTP path for both generic and explicit read gateway schemas.
Tests prove source verification and control isolation, not live speed.

After deploying v0.18.174 repeat:
"Read the current switch state and brightness level of Livingroom Light 2
directly from Hubitat. Do not change anything."

A successful filtered path should show:
- identity_scope=exact_label
- targeted_status.identity_lookup=filtered_unique_exact_label
- targeted_status.filtered_coverage.coverage_confirmed=true
- full_inventory_ms=0 and planning_ms=0
- current state attributes from hub_get_device for ID 7828

If it still falls back, inspect targeted_status.filtered_coverage; the
server may return an unpaged list without a terminal/total marker, or
may report a global rather than filtered total. In that case do NOT
infer uniqueness from one returned row. A stronger source identity API
or verified bounded index is needed before eliminating the full audit.
