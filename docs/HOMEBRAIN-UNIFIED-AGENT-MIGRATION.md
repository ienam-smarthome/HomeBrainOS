# HomeBrainOS — Unified Agent Migration

Status: incremental architecture migration, read-only V2 and production V1
write boundaries unchanged. v0.18.176 is the first offline golden-evidence
contract, not a native-tool-loop or unified-write cutover.

## Architectural decision

Build one source evidence plane and one policy-controlled execution plane,
with an interchangeable AI reasoner and dynamic MCP tool catalogue.

- Source acquisition: trusted READ operations, bounded event history,
  command reports, device/app settings, sensor dependencies and log gaps.
- Canonical case file: separate issuer from reporter; source timestamps,
  coverage, retention, cause uncertainty and source IDs travel together.
- AI reasoning: model chooses questions and native tool operations from a
  task-relevant LIVE catalogue plus further discovery. Host must still check
  tool effect, exact device identity, argument schema, budgets and provenance.
- Writes: reuse V1 verified control and confirmation/backup/readback gates.
  V2 test route remains read-only until a distinct migration approval.

## Stage gates

| Stage | Implementation | Exit criteria |
| --- | --- | --- |
| 0 Baseline | Recorded fixture replay, task catalogue and reference comparison | CI offline; clear source-versus-reference separation, ten or more task types, no sensitive fixtures |
| 1 Evidence | Generic command-to-state pairing, history-filter gaps, appId, app config, referenced sensors, restart/log coverage | Command by 4020 and report by 7790 distinguishable; 243 ms link; gaps remain explicit; no wrong issuer |
| 2 Tool surface | Native callable functions generated from LIVE MCP subtool schemas, dynamic discovery and host permission checks | No invented operation or ID authorised; model can acquire relevant reads and recover from failed tools |
| 3 Common execution | Shared read/write engine, V1 retained as fallback, verified batch commands and rules | All control, ambiguity, sensitive-write confirmation and backup/readback cases pass shadow equivalence |
| 4 Performance and hygiene | Model selection by task score and cost, portable evidence tools, tidy docs/workflows | >=30 live samples per task class; measured P50/P95, zero unconfirmed sensitive writes and invented causes |

## Provisional performance targets (not yet achieved)

- Named single-device status P95 below 2 seconds over >=30 cold/warm live
  samples. One 1.699-second result does NOT establish P95.
- Investigation P95 target under 30 seconds *only if* no available decisive
  evidence is sacrificed for latency. Track fact recall and omissions.
- Zero sensitive writes without explicit policy-gated confirmation; zero
  unsupported causal conclusions rendered as verified; gaps disclosed.

## Golden case — Livingroom Light 2, 28 October 2026

The following is **user-provided Claude investigation reference**, NOT yet
an independently captured, complete MCP transcript:

- FP400 inactive at 00:14:00.481 UTC (reference only until its own sensor
  event and verified ID are captured).
- command-off for device 7828 attributed by events to app 4020 at
  00:14:56.868 UTC.
- switch=off reported by Matter bridge source 7790 at 00:14:57.111 UTC.
- Command-to-state interval 243 ms, without proof of physical output.
- Stored 30-second inactive-off setting versus about 56.387-second
  motion-to-command interval. The extra 26.387 seconds are unexplained.
- Incident execution logs reportedly unavailable following firmware update
  and restart. Verified log/restart source coverage still needed.
- User-supplied verified setLevel(30) command around 23:42 UTC contradicts
  the unqualified claim that the level reduction could only originate on
  the Hue side. Clock alignment and exact source event require examination.

The golden fixture tests/fixtures/investigation_v2_light2_2026_10_28_golden.json
holds sanitised USER-SUPPLIED transcribed source rows, not a verified live
capture. Its reference_only_not_yet_source_verified entries are **not**
trusted canonical evidence. They must be replaced by independently fetched
host-projected source receipts in later stages.

Run the offline contract suite:

    python scripts/run_v2_golden_suite.py
    python -m pytest -q tests/test_investigation_v2_golden_contract_0_18_176.py

The gate checks source retention, typed links and filtered-history uncertainty.
It does NOT rate LLM narrative quality, prove the real incident's provenance,
call Hubitat, or run rules.

Golden task registry tests/fixtures/homebrain_golden_tasks_v1.json includes
status, history, hub health, MQTT conflict, multi-device, rules, control and
refusal scenarios. capture_required entries are PLANNED, not passing live
tests. Write tasks must first use mocked execution before explicit
confirmation-gated live testing.

## Deferred work requiring separate PRs

- Native model function calling, flat but bounded discovered subtool schemas.
- General source-first incident bundle with typed app-dependents, sensor
  history and log/restart coverage.
- Common V1/V2 read/write service and later production cutover.
- Actual redacted MCP transcript recording, model comparisons and live
  nightly automation. Do not schedule a live test without user approval.
- Opt-in historical journal app-log collection. The current code supports
  explicit per-app log collection, but this release does not enable it.
