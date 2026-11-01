# v0.18.322 — Stage 8.7 archived native command provenance

## Live diagnostic that triggered the change

The current Hubitat target-scoped event endpoint returned **zero raw rows** for each of command-off, command-on and switch on the requested older UTC incident date. The Historical Journal retained older switch reports, but its Stage 8.3/8.4 view previously suppressed all command event kinds, even though the journal's existing native-history read-through ingestion **can save** command-on, command-off and command-setLevel observations as `source=hubitat-mcp-command:app:<numeric_id>`. It records old source-declared times and later local receipt times independently.

## What this implements

- Extend **the existing consented Local Journal Shadow read** (30 days, one device ID, 50 returned rows) to also accept those exact native command origin markers. No new Hubitat queries, polling, app log reads, Cloud AI or device commands.
- For command records only, safely expose `recorded_issuer_app_id` from an **exact bounded numeric app-origin marker** and the command type. Other sources, invented app markers and missing source times fail closed. `command-setLevel` deliberately does not infer a target level from its archived value field (the journal's current native read-through does not preserve an independently authenticated setpoint).
- Distinguish `archived_native_command_record` from `reported_state_observation`; mark native state read-through reports separately from other journal stream observations.
- Display an explicit command count, native state read-through count and 50-row page-cap indicator, with clear **absence limitation** when no command records are retained.
- Preserve temporal-integrity warnings: a record recovered days later does **not** prove a device was online on its journal receipt date.
- Keep `history_complete`, `physical_execution_verified`, `causal_attribution_verified`, `missing_events_prove_inactivity`, and publisher approval false.
- Strictly sanitized output: no device/app labels, free-form command description, IP/MAC, tokens, source strings or unrelated device information.
- Synthetic regression tests for authentic-format read-through commands, forged marker rejection, late receipt, privacy, missing evidence and page caps.

## Phone acceptance

Upgrade to `0.18.322`, enter target device ID `7103` and run **Historical Shadow · Local Journal** with fresh consent. Look for **Archived native command records (bounded page)** and the event entries `Recorded command-off from app ID ...` if they exist. If none are found, do **not** conclude no OFF command occurred: the original source pages were empty and the journal only archives prior successful native reads when they happened.

Do not enable production investigation or declare unique causation based on command/source timing alone.