# HomeBrainOS 0.18.436 — MCP log-mode contract and restart evidence clarity

## Source-backed problem

The first ordinary Ask live replay on installed v0.18.435 correctly preserved typed Hubitat events:
05 Nov 2026 16:41:40 UTC (explicit critical-memory/reboot warning) and 16:52:15 UTC
(systemStart). It still made time-bounded `hub_get_logs` calls in `apps`,
`devices` and `hubActions` modes, all unsuccessful. The upstream MCP Rule
Server contract identifies these as *non-temporal* runtime/statistics/action tabs;
time-scoped historical app/device message content comes from `past`.
The original model draft remained unsupported about the memory-consuming app.

## Changes

- Before invoking MCP, reject model-selected `hub_get_logs` calls with
  `since` or `until` on a known non-temporal tab. Provide an error explaining
  `mode='past'` and optional `appId`/`deviceId` for historical lines, without
  issuing the invalid tool call. Unknown future modes remain resolved by the
  live MCP server rather than blocked speculatively.
- In the existing causal time-window normalizer, add bounds only to temporal
  `past`, `hubEvents`, `locationEvents` modes, not runtime/statistics tabs.
- Preserve verified typed Hub Events in chronological order even when the AI
  causal explanation is withheld. When a genuine explicit critical-memory/
  reboot warning precedes startup within 30 minutes, report that Hubitat's
  *announced reboot context* is verified, not that any app/driver is responsible.
- In both ordinary Ask and dedicated incident Technical details, distinguish
  app runtime-stat reads from time-bounded historical past-log reads. A
  successful request summary never establishes historical message coverage.
- Synthetic tests verify contract-safe normalization, rejected modes,
  dedicated incident app-log classification and event ordering.

## Boundaries, evaluation and rollback

No new MCP calls, automated monitoring, writes, configuration changes, or
paid-model escalation. App stats describe current runtime, not retained
pre-reboot process memory. The 05 November incident's underlying consumer
remains unverified. The recorded 45.9 s live investigation is a single
observation, not a performance distribution. User-graded cross-version
answer accuracy and latency improvement remain **NOT MEASURED**.

Rollback if tests or lived read-only evidence show any missing event, an
unexpected blocked valid mode, tool routing regression or unsupported causal
claim. Re-run one normal Ask and one explicit incident AI review against the
same retained incident with complete Technical JSON; audit actual `past`
message rows and retention separately.
