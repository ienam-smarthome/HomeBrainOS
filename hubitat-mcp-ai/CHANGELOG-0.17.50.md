# HomeBrain 0.17.50 — Opt-in historical app-log decisions

## Motivation

0.17.49 reconstructs the independent 12 October light OFF correctly in around 2.7 s. However, the requested app 4019 **historical lockout decision** remains unverified because the bounded Hubitat logs are empty. The opt-in Historical Journal already supports a persistent `/logsocket` stream for allowlisted apps, but the lockout investigation only queried its **device** event archive, never its **app log** archive.

## Changes

- New `archived_app_decision_evidence.py` reads persisted journal app-log rows for the exact application ID and anchored UTC interval. It **does not poll or alter Hubitat**.
- Return explicit readiness: journal not started, app capture not allowlisted, log socket connected at read, bounded app rows, app-log-specific capture gaps and successful/failed archive query.
- Keep message bodies out of public technical evidence. Expose bounded candidate categories and collector-received UTC time only; do not conflate a Hubitat log packet's unverified source time with the collector timestamp.
- The host-generated focal reconstruction now reports archived log capture readiness, rows, potential textual lockout/motion decisions, disconnection gaps and epistemic limits.
- A log *statement* is not proof that an eligible motion was suppressed or a real timer took effect. Handler references on state events also do not prove execution. Current app settings do not prove historical configuration.
- Failure and privacy regression tests include disabled capture, wrong-app rows, fake event-stream rows, local SQLite persistent allowlisted logs, redaction, gap windows and end-to-end prefetch.

## Activation (requires user action)

In Home Assistant, edit **Hubitat MCP AI** add-on options:

- `historical_journal_enabled: true`
- `historical_journal_capture_logs: true`
- `historical_journal_log_app_ids: "4019"`
- `historical_journal_retention_days: 30`

Retain the existing LAN-only `historical_journal_hub_url` and confirm journal events and logs streams can connect. Restart the add-on after saving. Permit relevant informational/debug app messages on the Hubitat side only for the short controlled test interval; monitor hub load and stop debug afterward if needed.

This cannot restore uncaptured 12 October logs. Do not change app 4019's 300-minute lockout duration as a side effect of configuring the journal. The intended three-minute duration requires a separate explicit configuration decision.

## Safe follow-up

After log capture is active, perform a new **user-controlled** button OFF event, allow an eligible sensor to activate normally, then ask HomeBrain to investigate that new local clock interval read-only. Do not assume an archived statement alone proves inhibition. Cross-check a later ON command (or an explicitly captured reject decision) before marking the effect verified.
