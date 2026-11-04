# HomeBrainOS v0.18.401 — Q1 typed-source field grounding

- A real registered hub-health read-only question on v0.18.400
  returned accurate driver-reported CPU/memory/DB/uptime figures
  but invented a precise temperature absent from `reported` fields,
  asserted overall health/alert absence, and overstated firmware
  freshness from installed/available driver scalars.
- Add a **universal typed-source field-attestation check**, shared
  across read-only status answers. It uses current-request successful
  scoped scalar source fields and individually identified device
  attributes, not an ad hoc Hub Info value cache.
- Handle missing numeric measurements, conflicting snapshots, source
  units, exact per-device switch/level claims, typed radio states,
  alert/health absence limitations, and firmware-report freshness.
  Preserve model authorship; only checkable contradicted claims change.
- Add a generic source prompt and privacy-safe correction counter.
  Tests use synthetic hub and other typed snapshots, device status,
  power, humidity, battery, missing units, failed sources, and
  conflicting identities. No Hubitat/HA/router reads or writes made
  as part of release development.

Observed baseline 11.139s / 2 model rounds / 1 read; **post-release
live grounding and latency NOT YET MEASURED**. Green CI does not
prove a system-wide correctness score or independent physical health.
Source review: `docs/ANSWER-QUALITY-Q1-TYPED-REPORTS-20261104.md`.
