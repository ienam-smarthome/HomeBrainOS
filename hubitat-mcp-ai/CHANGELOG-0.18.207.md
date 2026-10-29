# Hubitat MCP AI v0.18.207 — Read-only performance statistics as distinct evidence

## Motivation

The live v0.18.206 Google Nest Hub investigation completed in 13.080 seconds, successfully read 5 MCP sources, and correctly identified 7 warnings in a 9.836-second cluster with 3 source-attested Calendar Notifier commands. The explanation was accurate about proximity, but the generic driver load warning did not identify the executed callback or measured CPU usage. The remaining high-value information source was **Hubitat Logs → Device Stats / App Stats**.

Upstream MCP exposes these cumulative performance tables via `hub_get_logs(mode="devices", deviceId=<verified ID>)` and `hub_get_logs(mode="apps", appId=<source-attested ID>)`. The former standalone `hub_get_performance_stats` operation is retired. V2 previously sent all `hub_get_logs` responses to the severity-log adapter, which could discard or misclassify typed runtime rows.

## Implementation

- Add `native_runtime_stats.py`, a fixed source adapter for exactly `hub_get_logs` responses with `mode=devices` or `mode=apps`. Project only source-row numeric `pct`, `total`, `count`, `stateSize`, `events`, a bounded display label, ID and safe numeric table totals. Drop credentials, URLs, IPs, raw settings, unrecognised row content, arbitrary strings and untrusted metadata. Flag empty/malformed data explicitly as unavailable, never as zero usage.
- V2 now separates runtime-table responses from conventional WARN/ERROR log lines. The model can choose a source-attested, read-only device/app runtime-stat read after a warning, without automatic execution, alternate keyword routing or expanded write permissions. It must omit `level` in these modes.
- Scope target-specific performance evidence to the verified device ID and, for app stats in a device investigation, independently verified calling app IDs. Add typed source-read receipts to model highlights, factual ledger, general claim catalog and source-authoritative incident packets. Numeric claims are explicitly labelled cumulative-snapshot observations, never historical incident-time CPU attribution.
- Continue preserving generic warning provenance, incident cluster/command correlations, privacy filtering and all previous source/causal guards.
- Tests cover real-world source shapes, app/device scope isolation, omission of private fields and invalid numbers, no bogus zero CPU on missing data, typed payload dispatch, claim catalog and report source receipts.

## Evidence limits

Hubitat's performance page is a cumulative, potentially cached snapshot, not a time-aligned recording at the 09:00 warnings. A high busy share can support additional investigation, but a single number cannot establish which application or device driver callback caused an earlier warning. The source may vary with hub uptime and reset on reboot. The incident remains unattributed without independently discriminating runtime data.

Experimental V2 remains strictly read-only. No Hubitat device, rule, configuration, production Main Ask route or permission is modified.
