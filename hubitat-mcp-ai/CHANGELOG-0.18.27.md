# v0.18.27 — Close historical command-history evidence obligations before final synthesis

## Live regression: v0.18.26 (17 October 2026)
The user's app 3950 / device 7103 historic OFF verification returned after 43.5 s (six paid DeepSeek rounds, six read calls) and correctly marked its verdict unresolved, but source coverage identified **command_history unchecked** despite the explicit query asking who issued the OFF command. The evidence included switch state history and three successful zero-row app/device log queries. The model additionally called a device-originated switch-state event an 'acknowledgement'; that event by itself does not establish transport or physical acknowledgement.

## Underlying problem
The repository already has a tested, read-only, exact device-command event reader (`DeviceHistoryService._read_command_events`), which can query `command-on/off` separately from `switch` events. Historical named-app execution verification was properly routed to the model in v0.18.25, but the model never invoked command-history evidence, and the general API only flagged the missing required source *after* final answer. Consequently additional model rounds/read attempts did not close the actual obligation.

## Correction
- Introduce `pending_historical_command_read`, a generic, pure, receipt-driven evidence obligation planner. It recognizes explicit historical app command verification, requires the user to identify an exact numeric target **device** and explicit ON/OFF command, and verifies matching current-request device ID, label and lookback from successful existing read receipts. It never guesses a device or history horizon.
- At the existing general `_final_answer` read-only source-completion phase, invoke the already-existing exact command-history reader once if the Hubitat device read gateway is actually available. Return the bounded command rows to the final synthesizer along with warnings that state events, downstream listeners and empty command pages do not themselves establish or refute command causality.
- Skip duplicate command reads, including previously failed attempts. Keep missing/unavailable classes explicitly unresolved. An empty successful stream counts as a source class checked but is not a verified command/noncommand verdict.
- Preserve the established confirmation and effect-check architecture: absolutely no Hubitat writes, tool privileges, provider billing changes, or change to model Auto/Free/Paid selection. No additional model planning round is required.

## Testing
Unit tests cover the real v0.18.26 incident, device identity disambiguation, missing source horizon, evidence-only device/labeled target constraints, duplicate reads, failed reads and no-gateway behaviour. The production `_final_answer` unit test verifies the required read is executed once and inserted as actual tool evidence before synthesis. Merge only when all three required GitHub CI workflows pass; live read-only Home Assistant validation is separate.
