# HomeBrainOS v0.18.178 — focus investigations on the latest attested switch incident

## Live failure reproduced

The 28 October v0.18.177 investigation of Livingroom Light 2 (device 7828)
retrieved 34 source-attested commands and 39 state reports, including:

- 2026-10-28 00:14:56.868 UTC — command-off by app 4020
- 2026-10-28 00:14:57.111 UTC — switch=off reported by bridge 7790
- Reported command-to-state difference: 243 ms

Nevertheless, the source-config collector selected app 4129 and the
logs collector selected button app 1252. Config for 4129 did not provide
motion sensor selections. A 35-second model planning call timed out with
21,374 characters of planning context. Identity discovery took 21.1s,
and the full result took 57.872s. The source histories were not
independently complete, and physical switch action was not proven.

## Cause and fix

The config selector previously ranked ALL historic command issuers by
how near they were to an adverse networkStatus transition (and otherwise
by frequency), which can prioritise an old, unrelated incident. The log
selector chose the numerically smallest historic command issuer.

The common `focused_switch_command` evidence helper now selects the
command explicitly time-paired to the latest Hubitat-reported switch
transition (same device and state; default 2-second causal *association*
window). Both configuration and log evidence use the same focus and
independently verified device ID. If the latest switch event is
unpaired, neither stage silently substitutes a different historical
issuer. With command records but NO switch state reports, the latest
command can still be investigated as an unpaired command, without
claiming a switch or successful automation.

For large undated investigations, ONLY the model's read-planning view
may coalesce older records while retaining the last-attested incident,
source-typed record references, diagnostic source limits and context
summaries. The complete canonical case and source-backed answer are
unchanged and contain all observations. Explicit historical incident
windows retain their original complete planning view. The most recent
typed command-state pairs appear first; older prefix order cannot
suppress the latest crucial pair.

## Invariants

- No device, room or app-specific term routing.
- No unverified device ID, write, management gateway or other permission.
- No promotion of source 7790's switch report to initiating command.
- No claim that the current app settings were effective at the incident
  time, or that a 243-ms time pair proves physical actuation.
- No raw logs, secrets, broad device inventory or private app settings
  exposed to the model.

## Acceptance

Replay synthetic history with competing app 4129 network-offline history,
button app 1252 commands, and a newer 4020 OFF/7790 state pair:
- config lookup and log scope target app 4020;
- a wrong target ID yields no authorised issuer;
- an unmatched latest switch report prevents selection of a historic
  command as though it caused the latest transition;
- large model context is reduced, while the full case retains every
  typed observation and the latest 243-ms command-state pair;
- command-only cases remain explicitly unpaired;
- complete CI and replay gates pass.

After deploying v0.18.178, repeat the same Livingroom Light 2
read-only causal investigation; inspect
`bootstrap_diagnostics.controller_config.incident_focus`,
`bootstrap_diagnostics.controller_config.issuer_id`,
`bootstrap_diagnostics.controller_logs`, `controller_sensors`,
`planning_diagnostics.input_chars`, and total runtime.

A further performance milestone is cold causal device identity discovery,
which currently still uses the complete identity inventory. Do not weaken
uniqueness proof or substitute brittle wording detection to reduce latency.
