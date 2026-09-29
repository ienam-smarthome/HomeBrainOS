# Hubitat MCP AI 0.16.72

## Summary

0.16.72 keeps the 0.16.70/0.16.71 four-tool, normally three-model-round broad-performance architecture and fixes the remaining grounding/context defects exposed by the 0.16.71 live proof.

## Changes

- Replaced FIFO performance-packet eviction with per-source bounded budgets inside the existing 32k private synthesis packet.
  - `hub_get_metrics`: 7.5k
  - `hub_get_performance_stats`: 11.5k
  - `hub_get_jobs`: 7.5k
  - `hub_get_logs`: 4.5k
- Preserves all four source identities under packet pressure instead of dropping the oldest source; current metrics can no longer be silently evicted merely because they were read first.
- Added privacy-safe counters for packet source reuse and metrics-payload reuse/missing state.
- Added a current-metrics contradiction repair. When `hub_get_metrics` succeeded and the retained payload contains current values, a false “memory / temperature / database unavailable” statement is replaced with the retained measured values. If the detailed payload is genuinely absent, HomeBrain reports a synthesis-context limitation rather than claiming the hub lacks those metrics.
- Prefer compact current-turn log evidence when already present, while retaining the bounded private log payload as a fallback.
- Fail-close remaining 0.16.71 wording/prescription gaps without crossing Markdown table cells:
  - “performance bottlenecks have been identified” → evidence-bounded observations/outliers,
  - “Critical Performance Issues” → neutral observations,
  - unsupported “severe synchronization” language,
  - same-second scheduling described as scheduling alignment rather than proven simultaneous execution,
  - repeated triggers no longer labelled an “efficiency issue” without evidence,
  - frequent reporting no longer promoted to “background load”,
  - “Stagger the Block Ticks” and `should be offset` are inspection-first without configuration evidence,
  - “Shift System Tasks / Move ... to different offsets” is inspection-first without configuration evidence.
- Added the full 0.16.71 live failure as an end-to-end regression, including metrics recovery and intact three-column recommendation-table assertions.
- Added a packet-pressure regression proving metrics, performance, jobs, and logs all remain present simultaneously.

## Live acceptance target

Run:

`Analyse my Hubitat performance and recommend improvements.`

Expected broad path:

- normally 4 tool calls,
- normally 3 model rounds,
- retained `hub_get_metrics` values available to final synthesis,
- no false missing-memory/temperature/database note when those fields were measured,
- no unsupported bottleneck/critical/severe/efficiency/background-load claims,
- no direct scheduler-offset prescription without configuration evidence,
- Markdown recommendation table remains intact.
