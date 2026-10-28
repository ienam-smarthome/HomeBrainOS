# HomeBrainOS v0.18.186 — MCP log mode contract and evidence window

## Live regression basis

At 21:15 UTC on 28 October 2026, the v0.18.185 native agent
correctly resolved Google Nest Hub 7934, but issued incompatible log calls
with `mode=devices` and `level`. The MCP Rule Server recorded:
"Parameters level do not apply to log mode 'devices'". Two calls failed
and two duplicates were rejected. The only successful log read returned
100 rows (98 INFO, 1 WARN, 1 ERROR) spanning approximately 21:12–21:14,
with no target-specific Nest warnings. Those observations cannot establish
that the 17:52–19:55 Nest warning interval seen in an earlier run has ended.

## General improvements (no question-word routing)

- Host-side validation of concrete `hub_get_logs` operation combinations,
  not just the general gateway JSON schema. When a severity level is
  supplied, mode must be `past` (or omitted, default past). Logs-page
  tabs such as `devices`, `apps`, `scheduledJobs` or mixed tabs
  cannot be combined with a severity level.
- The model gets specific, reviewed remediation: switch to
  `mode=past, level=warn` or `level=error` with a verified deviceId
  and bounded result limit. Alternatively omit `level` for mode=devices.
  Incompatible calls are rejected before any MCP request and never create
  self-inflicted MCP Rule Server error logs.
- The native system instructions explain the operation mode contract.
  Tool receipts now include the scoped deviceId or appId filter so the
  coverage can be audited without guessing what was queried.
- Target-focused evidence includes the actual returned log timestamp window,
  sample size and level/mode scope even when the selected target has no
  warning in that small sample. It explicitly prevents an inference that
  earlier historical warnings have disappeared.
- New live-shaped tests cover invalid cross-tab arguments, safe allowed
  combinations, bounded recovery using the model-selected compatible call,
  and negative evidence restricted to the returned sample.

## Safety / acceptance

This remains experimental V2, read-only, and independent of production Main
Ask. No devices or automation configurations are changed. These changes
prevent an identified query misuse; they do **not** yet prove Google Nest Hub
runtime root cause, independent claim-evidence verification, or model parity
with Claude. Live acceptance must confirm that a corrected `mode=past`
query retrieves the relevant historical warnings and that the model
interprets those sources with appropriate time and causal limits.
