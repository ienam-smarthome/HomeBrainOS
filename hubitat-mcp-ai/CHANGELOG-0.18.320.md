# HomeBrainOS v0.18.320 — Stage 8.5 target-scoped historical command-evidence shadow

## Live source finding
The prior consented local journal read returned six switch reports carrying source-declared timestamps from much earlier than the collector's arrival (apparent discrepancy of many days), with receipt-order inversions and recent collector gaps. These journal rows are **reported state observations**, not authentication of physical switch transitions or proof of which automation issued a command. The local journal's app-log retention defaults to 48 hours, so it cannot be presumed to cover an older incident.

## New read-only comparison
Live Shadow now offers a **separately consented Command Shadow** view for a numeric Hubitat device ID and **UTC incident date**. It makes exactly three fixed, target-scoped, read-only Hubitat gateway event requests: `command-off`, `command-on` and `switch` using the existing `hub_list_device_events` suboperation. Each source page is limited to 50 records. The selected UTC day must be within the last 30 days. These are Hubitat *reads*, not actuator commands. The generic history gateway remains unchanged.

The projection returns only bounded event kinds, normalised UTC source-reported timestamp, explicit switch state or command name, and numeric issuing app ID if recorded in structural `producedBy` metadata. It never sends free-text event descriptions, room labels, full producer names, IP/MAC, secrets or other devices' rows to the dashboard.

The source API is paginated/newest-first and filtering may omit older events or have retention limits; **no returned command is not proof no command was issued**. Exact command-event recording is distinct from device receipt, physical actuation, the cause of network loss, and authenticated clock accuracy. Even a command and OFF report at nearly the same time are only temporally associated without independent command-correlated confirmation. The app's upstream trigger is not established from device event pages.

## Safety contract
- Per-run opt-in checkbox; same-origin JSON request; selected numeric device ID and bounded UTC day.
- Hardcoded read-only gateway and operation names; no client-selected operation or actuator calls.
- No Cloud requests, model reasoning, log reads, config changes, journal writes, source code fetch or publisher activation.
- Result reports source read failures separately from zero matches.
- Tests mock the gateway and Cloud transport; no live Hubitat commands or HTTP reads in CI.

## Manual acceptance
Upgrade to v0.18.320. Under **Live Shadow → Command Shadow**, enter device ID 7103, select **2026-10-12 (UTC)** and tick the **separate** command-read consent. Select **Compare command and switch events**. Send source read statuses and any dated commands. If the selected day is not represented by these bounded pages, do not assume the command never happened. Archive/source time contradictions must remain flagged for independent review.

Rollback: revert this PR to v0.18.319.