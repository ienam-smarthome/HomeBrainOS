# HomeBrainOS V2 Alpha155 package candidate — 23 November 2026

## Status

- Source-projection PR #1742 is merged into `main`; its four exact-head CI workflows passed.
- A separate Alpha155 package candidate is being prepared on branch
  `agent/v2-alpha155-prospective-package-20261123`.
- The candidate version is `2.0.0-alpha.155`.
- The prospective pack is `alpha155-prospective-v1`, with ten distinct
  `a155-01` through `a155-10` prompts.
- The acceptance workspace is isolated at
  `/data/homebrain-v2-alpha155-acceptance`.
- This is code preparation only: it is not installed, released, captured or promoted.

## What Alpha155 tests

1. **Memory arithmetic:** returned free-memory samples in an 80-minute
   inclusive window; arithmetic mean, minimum, maximum, range, latest-sample
   delta, UTC cutoff and sampling gaps. The latest history sample must not be
   called a live reading.
2. **Battery inventory:** distinct IDs with numeric battery values in an
   inclusive range, missing versus nonnumeric values, and actual page/hasMore
   coverage.
3. **Current snapshots:** separately identify two lights' stored switch and
   brightness fields; no physical illumination or dated-event inference.
4. **TRV event interval:** newest two recorded operating-state samples and
   exact elapsed seconds; no invented intervening trajectory.
5. **Contact chronology:** newest OPEN/CLOSED reports, chronological row order,
   earliest/latest timestamps and significant gaps; no continuity claim.
6. **Past WARN logs:** source grouping with returned rows, matched count and
   aggregate total kept distinct; no invented scan/retention scope.
7. **Command/health chronology:** command and health-status rows ordered by
   source time; health status is not a physical measurement or proof of a
   missing switch transition.
8. **Application execution:** exact installed app identity and dated evidence,
   distinguishing app logs, native commands and device reports.
9. **Current heating attributes:** thermostat/TRV setpoints and operating
   states, with unavailable attributes explicit and historical cause separate.
10. **Energy history:** newest two dated energy-total samples, same-metric
    arithmetic only, and stored energy/lastActivity kept distinct.

The pack contains prompts and labels only in the private sealed study. It does
not contain answer keys, expected source values or raw household evidence.
The old Alpha153/154 packs and original captures remain frozen and cannot be
used as prospective post-change evidence.

## Safety and evidence boundaries

- Acceptance still performs the existing server-side read-only-client
  preflight before each first attempt and records its original permission
  receipt. This is source-reported evidence, not an independent penetration
  or enforcement test of the dedicated token.
- The user must configure a dedicated per-client token with Read ON and
  Write OFF before any live capture. Do not use a general-purpose token.
- The new projections publish only from existing successful source receipts;
  they add no Hubitat reads, retries, model rounds, writes or automation changes.
- V1, heating schedules, ventilation, blocking schedules and native write /
  approval policy are unchanged.
- Raw Technical JSON, device/app labels and household data remain private and
  must not be committed.

## Remaining release gates

1. Exact-head CI for this Alpha155 package branch; fix all failures before merge.
2. Review package/runtime/config version identity and acceptance route isolation.
3. Install the exact Alpha155 package in Home Assistant; do not treat GitHub CI
   as installation or first-answer evidence.
4. Independently verify the dedicated MCP token cannot perform native writes.
5. Seal the new private Alpha155 manifest and capture each first answer once.
   Do not replay, retry, refreeze or relabel an old cohort.
6. Export the untouched original captures and grade each answer against its
   original source receipts.
7. Retain the promotion charter: at least 90% grounded atomic factual claims,
   at least 80% useful complete first answers, zero unsupported definite
   causes and zero write/approval regression.

Until all gates pass, Alpha155 remains an experimental candidate and V1
remains the maintained installation path.
