# 0.17.84 — Bounded investigative follow-up before unresolved focal stop

## Problem
The 0.17.83 regression for Livingroom Light 1 on 14 October correctly reconstructed the archived collector OFF/ON/OFF/ON sequence and SenseCap D1 command, but the technical counters showed `skills_early_focal_stop=1`, `model_rounds=1`: HomeBrain stopped before checking the recorded command producer's current topology.

## Improvement
- Add a **host-owned, evidence-derived read selector** for specifically dated ON investigations with a verified command-producing app but no verified physical-state timestamp.
- If the source-catalog permits, perform **at most one read-only `hub_get_app_config` for the command-producing app** with `includeSettings=false`; verify the returned app ID and retain only bounded sanitized, noncredential configuration descriptions.
- If the persistent journal is started and the *same* app ID was explicitly allowlisted for log collection, also query at most one bounded archive-log window and retain **counts/coverage only**, never log-message content.
- Avoid duplicate reads, check the original incident date, obey existing focal source and evidence classes, and preserve the “no source-timestamped state proof” causal stop. No unrestricted model loop or command execution is introduced.
- The deterministic partial answer explains current producer configuration separately from historic provenance; current settings never prove a past MQTT input, physical state or command delivery.
- Add regression tests for correct app ID, stale-day rejection, deduplication, secret redaction, opt-in log lookup, and answer integration.

## Scope
This is the **first runtime integration** of evidence-led decisive follow-up, not a complete autonomous investigation planner. It introduces no new Hubitat privilege, device mutation, setting change, journal schema or retention change.

## Validation
Require passing add-on tests, full Python suite, metadata and container smoke test. Post-install, rerun the 14 October incident and confirm an `investigator_producer_config` receipt appears, or a documented unavailable reason. Where app-log capture is not allowlisted, no archive-log contents are queried.
