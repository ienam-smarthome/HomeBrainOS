# Hubitat MCP AI 0.16.120

## Changes

- Do not interpret timezone-less Hubitat log strings as UTC event timestamps. Only explicit timezone-aware or numeric timestamps are eligible for UTC chronology; scoped audit rows with future-dated event times more than 60 seconds beyond the audit checkpoint are withheld from time-based ordering, while their warning/error messages remain visible.
- Include timestamp-integrity counts and limited raw examples when data have ambiguous timezone, no timestamp or apparently future timestamps. Do not assume a one-hour BST correction without verified source timezone metadata.
- Prevent spurious SenseCap D1 recovery claims based on misinterpreted or future-dated success logs.
- Add exact device ID/name pairs from the existing detailed inventory so label-only ADB warnings can select a bounded read-only follow-up when exactly one live identity matches.
- Prioritise new device/app failures and sample at most one unchanged offline device when a previous audit establishes that the status is unchanged; all offline states are still reported.
- Add source-grounded Dehumidifier 1 Zigbee METERING_CLUSTER and Google TV Streamer ADB next-check guidance without assigning undocumented error causes, changing drivers or executing repairs.
- Keep unsupported historical-log coverage unverified and all Hubitat mutation/confirmation safeguards intact.

## Validation

- Regression tests cover timezone-less local times, explicit offset parsing, apparently future timestamps, SenseCap recovery chronology, adaptive ADB and offline target selection, duplicate label ambiguity and safe Zigbee investigation.
- CI full Python suite, metadata checks and add-on smoke test must pass before merge.
