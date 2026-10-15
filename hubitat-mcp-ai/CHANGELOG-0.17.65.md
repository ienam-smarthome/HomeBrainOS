# HomeBrain v0.17.65 — historical source selection and useful reported health

## Historical sensor discovery
- Report why a configured-automation sensor was not selected: no known
  topology, no matching configured target/trigger, or no matching
  capability-verified identity in the cached inventory.
- Include bounded candidate-disposition diagnostics and plan up to four
  validated occupancy candidates instead of assuming the first two
  same-room sensors cover the requested event.
- Probe two primary historical windows first. Only if those windows were
  **actually verified by the server** and both returned no events may
  HomeBrain probe up to two additional ranked sensors. An unsupported
  window never proves sensor inactivity and cannot trigger this fallback.
- Record `causal_historical_sensor_fallback_reads` and expose
  `initialProbeSensorIds`, `fallbackProbeSensorIds`, and
  `configuredSelectionGap` for source-level troubleshooting.
- Sensor configuration remains a discovery hint, never execution proof.

## Event relevance
- Skip a distant, independently occurring closing-OFF command/app-log
  investigation when the request names a historical ON and the later OFF
  is more than two minutes afterward. That later OFF is not a predecessor
  cause of the requested ON.
- Preserve short-interval independent OFF provenance, the separate OFF path
  where a genuinely preceding OFF is found, and questions explicitly asking
  why the light switched OFF.
- Record `causal_irrelevant_off_skipped` when an irrelevant later-OFF
  follow-up is omitted.

## Device health synthesis
- Preserve a narrow, target-ID-matched snapshot of reported driver
  attributes from a successful targeted `hub_list_devices` lookup
  (healthStatus, mqttStatus, switch, lastSeen, lastActivity, dataAgeSeconds).
- Show those reported values and read timestamp in the deterministic device
  diagnostic answer, explicitly separating a driver attribute read from
  proof of fresh physical transport or when that attribute was measured.
- No status is invented if source data lacks it. Identity-mismatched state
  snapshots are rejected.

## Safety
All work is read-only. No Hubitat devices, rules, apps or settings are
changed, and write confirmations remain unchanged. Historical event
retention and the initiating cause remain dependent on what the server
can actually verify. New tests are synthetic; live retesting is required.
`general_task_engine_enabled` stays opt-in.
