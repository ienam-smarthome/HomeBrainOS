# HomeBrain 0.17.40 — Canonical historical event consolidation

## Live root cause

The 0.17.39 Livingroom Light 1 investigation succeeded (12.2s, seven
tool calls) and finally read historical light states and command events.
However, its structured lockout collector falsely returned
`no-focal-off-observed`, preventing time-scoped app-4019 logs and local
motion/controller correlation.

The underlying device-history service supplies
`temporalAnalysis.intervals`; the compact evidence receipt publishes
the same interval rows as `temporalAnalysis.observedIntervals`.
The collector was reading **only the receipt-format key** from its
**native-format tool result**. The successful historical fetch was thus
mistakenly treated as containing no completed OFF interval.

## Architecture

- Introduce one canonical interval accessor that accepts native
  `intervals` and audited `observedIntervals` shapes. The same
  accessor feeds both observed interval counts and newest OFF boundary
  selection. This removes a source-shape disagreement instead of
  adding case-specific text post-processing.
- Preserve matched **OFF command provenance** as a separate evidence
  class. The native command rows identify app **1251, button 1 pushed**,
  issuing an OFF command 193 ms before the *latest* OFF state report
  at **23:49:27.529 BST** on 12 October 2026.
- The earlier OFF at **23:49:12.284** also follows an app-1251
  OFF command at **23:49:11.898**, with a later ON command at
  **23:49:18.988** and ON state at **23:49:19.140**.
  Distinguish these two OFF transitions rather than declaring the
  earlier one the newest event.
- A verified app command producer is not independent proof that a
  physical button was pressed, that motion activated, or that app 4019
  engaged a three-minute lockout.
- Once a focal OFF exists, the existing bounded app-log and Historical
  Journal correlation paths are eligible to run. No new broad
  discovery, full-hub polling or unsolicited device actions are added.

## Regression tests

- The same native and technical-receipt interval rows yield the same
  latest completed OFF boundary.
- Command producer app 1251 is matched to the correct latest OFF with
  the correct millisecond difference; stale commands are excluded.
- A simulated end-to-end host prefetch with native-format history
  reaches the app-4019 bounded execution-log check, retains the
  command producer and does not falsely claim lockout execution.
- Empty history remains unresolved, not fabricated.

## Safety

Read-only; no Hubitat automation or settings modifications, history
migration, capture-rate changes or YAML updates. The existing seven-day
and 200,000-row Historical Journal retention stays unchanged.

## Live test

Update HomeBrain to 0.17.40, repeat the exact app-4019 historical
manual-OFF/motion-lockout investigation and send Copy technical.
Expect a `homebrain_motion_lockout_investigation` receipt with
`focalOff`, `focalCommandProvenance` and bounded app-log coverage
(or an explicit source failure). Historical lockout engagement should
remain unverified unless contemporaneous decision evidence exists.
