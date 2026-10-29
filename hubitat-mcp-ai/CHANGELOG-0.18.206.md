# Hubitat MCP AI v0.18.206 — warning-cluster command provenance

## Live evidence (29 October 2026)
The 09:24 Native V2 test of Google Nest Hub (device 7934) retrieved 8 source-reported excessive-load WARN rows: an earlier 06:01 occurrence and 7 rows between 08:59:59.642 and 09:00:09.478. All 8 had at least one safe device-state observation within 2 seconds. The model verified historical issuers Adhan Player (app 1679) and 00 Google Calendar Notifier (app 4080). In the newer 9.836-second warning cluster, Calendar Notifier issued three source-attested commands:
- setVolume at 08:59:59.657, 15 ms after the nearest reported WARN at 08:59:59.642
- speak at 09:00:01.109
- setVolume at 09:00:07.808, 15 ms after a WARN at 09:00:07.793

The previous answer mentioned three near-warning app commands only as an aggregate and instead emphasised an Adhan Player refresh burst ~14 hours earlier. Thus HomeBrain retrieved the important discriminating evidence but presented an irrelevant distant event as its primary activity lead.

## Change
- New `native_incident_command_temporal.py` builds source-receipt-derived *distinct* warning timestamps, groups adjacent warnings into bounded observation clusters (15 seconds maximum adjacent gap), and independently correlates only commands with verified `producedBy.appId` in a device-scoped event read. Repeated read receipts are de-duplicated, raw command arguments, device-state-only events and private media metadata are excluded.
- Warning clusters are evidence **groupings**, not independently measured CPU incidents. For each cluster, report observed WARN row count and time span, command counts by verified app ID, and signed source-timestamp separations from the nearest actual warning. Report incompleteness and unverified source-clock alignment. **Never infer** driver callback, CPU usage or actual cause from timing.
- Add an independently receipt-backed near-warning command-cluster fact to the incident claim ledger. The generic warning report prioritises the closest source-attested app activity, and shows older unrelated command bursts only when no command near the latest cluster is observed.
- Regression tests replay the 8-warning/two-cluster/three-command live trace, 15 ms pairs, unrelated scoped source exclusion, deduplication, privacy and correct causal uncertainty.

## Scope and limits
No new MCP operations, inferred device IDs, writes, production Main Ask changes or Hubitat automations. Experimental V2 remains read-only. Driver source is still unavailable, so the initiating callback and CPU mechanism cannot be confirmed. Full GitHub CI and a new live trial are required before claiming runtime performance improvements.
