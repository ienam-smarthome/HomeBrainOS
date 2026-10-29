# Hubitat MCP AI v0.18.208 — Verified target evidence anchor and performance scope

## Live 29 October 09:57 evidence (v0.18.207)

The V2 model retrieved 7 successful source reads: 8 Google Nest Hub (7934) generic excessive-load WARN rows, device cumulative runtime stats (pct=89.48085758694425, count=20,253, total=47,727,579 source units), 3 Calendar Notifier commands during the 09:00 cluster and an unfiltered App Stats page containing Google Calendar Notifier (app 4080, pct=7.073027573076396, count=829, total=1,977,482 source units).

Nevertheless `focus_ids=[]`, `resolved_devices=[]`, `incident_attribution_evidence=null`: the host only anchored focus from `hub_get_device` and named lookups, not actual source-confirmed, device-scoped WARN, device-event and runtime rows. Its model-only answer then timed out at 8 seconds and published a general claim fallback including an irrelevant SenseCap D1 warning. Four rejected proposals and 32.2 seconds total further reduced performance. These percentages are reported *within different Hubitat runtime tables*; **neither measures total hub CPU percent or proves the 09:00 cause**, and they must not be added or directly compared.

## Structural improvements
- Expand `verified_device_focus` to independently approved device-filtered `hub_get_logs(mode='past')` warning groups with matching **device** source IDs, `hub_get_logs(mode='devices')` with matching runtime device row IDs, and `hub_list_device_events` with a matching device-produced event row. The user's question must explicitly mention that numeric ID or an independently returned exact, multiword device label. Reject unfiltered logs, mismatched/failed reads, app-only command histories, unverified ID and generic hub audits. No keyword routing, inferred IDs or auto reads.
- Record source kinds in `verified_focus_receipts`, retain the original device-configuration focus contract. With focus correctly bound, existing host-authoritative generic warning report and zero-ms skipped final model synthesis work for all these source receipts.
- Use one shared helper for matching device/app performance-stat evidence. Target device rows and independently verified device event-command issuers are the *only* allowed rows in focused highlights, incident packets and general fact catalogs. An unfiltered `hub_get_logs(mode='apps')` page can provide an attested caller's row, but unrelated apps are excluded. Scope from an explicit `appId` or `deviceId` filter must still match a returned row—never allow an unrelated scoped response to override identity safety.
- Filter user-visible log coverage WARN details to focused device while preserving sample size, global severity counts and incompleteness disclaimers.
- Preserve source percentages as cumulative, differently denominated runtime-table statistics, not incident-time CPU measurements. Do not attribute generic driver WARN cause without separate evidence.
- Add generic identity-matching unit cases, negative scope/audit/alias cases, broad app-stat source consistency and complete end-to-end model-chosen READ replay with no unnecessary model-only synthesis.

V2 remains an explicit experimental read-only investigation flow. No production Main Ask or Hubitat devices/apps/automations are changed.
