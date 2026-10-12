# HomeBrain 0.17.41 — Historical evidence semantics and source clocks

## Cross-domain evidence integrity

The 0.17.40 live Livingroom Light 1 investigation now correctly reconstructs
an OFF command and native event state, and reads two bounded app-4019 log
entries plus six scoped Historical Journal streams. But a valid observation
is not necessarily a valid test of an automation's motion lockout:

- The native OFF state report was **23:49:27.529 BST** (UTC+01:00), whereas
  the output displayed **22:49:27.529** without identifying UTC. Journal
  events are collector-received UTC, not necessarily source event time.
- Linptech Kitchen sensor motion active at **22:51:09.904 UTC** corresponds
  to **23:51:09.904 BST** (about 102.4 s after OFF), but no authoritative
  activation-source role was established for app 4019. A sensor capable of
  keeping lights on need not be allowed to turn them on.
- App 4019 historical log retrieval reported **two rows**, yet only their
  count was passed into the collector's final synthesis; without reviewing
  their contents the model cannot claim they demonstrate or exclude a
  lockout decision.
- The Historical Journal reports **two capture gap windows** per source
  response. An empty sensor response and no recorded ON transition do not
  prove the source was continuously quiet.

## Changes

- Preserve the actual source clock offset from a native Hubitat OFF event
  as `focalOffHubLocal`, alongside the unchanged UTC `focalOff` used
  for queries. Convert journal reception times into that source offset
  only for human display, keeping `timestampBasis=collector-received`.
  No system-local timezone assumption and no change to query windows.
- Add bounded, structured `motionCorrelations` with device identity,
  delta after OFF, reception timestamp basis, displayed offset and
  **independently verified activation eligibility**. Current room/config
  name matching is not authoritative proof of activation eligibility;
  it is explicitly unverified.
- Tighten the shared `investigation_coverage` assessor so time-correlated
  sensor motion alone does **not** satisfy a requirement for actual
  activation-sensor evidence. It remains checked-but-unverified until
  role metadata is genuinely available.
- Mark app-log row counts as distinct from reviewed decisions with
  `decisionContentReviewed=false` and add scoped Journal gap coverage.
  The answer must not infer lockout execution, a negative execution-log
  search, or continuous inactivity from these incomplete sources.
- Add regression coverage for UK BST versus UTC, 102.375-second
  correlation, eligible versus unverified sensor roles, and strict
  refusal to treat naïve timestamps as source clock evidence.

## Safety

Read-only; no new device or automation reads, no commands, no metadata
migration or journal retention changes. Existing seven-day / 200,000-row
Historical Journal retention is preserved.

## Next step

A future generic app-log decision extractor and authoritative
sensor-activation-role source would permit a genuine execution/behaviour
claim. This release does not fabricate those sources.

## Live validation

Update to 0.17.41, repeat the exact app 4019 historical manual-OFF
investigation. Verify hub-local **23:49:27.529+01:00**, preservation of
the producer app 1251, journal collector-time qualifiers and
`investigation_coverage.requirements[motion]` **checked-unverified**
unless real activation eligibility was established. App 4019 lockout
execution remains unknown without a decision/execution record.
