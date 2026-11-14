# HomeBrainOS V2 alpha.97 — event-time fidelity in existing final audit

**Date:** 14 November 2026. **Scope:** V2 Preview only. No V1 changes, live Hubitat tests or real source data added to the repository.

## Evidence and problem

Three owner-supplied alpha.96 tests were reviewed against PRIVATE original read receipts. The basic current-state read completed correctly using one `hub_list_devices` call. Two causal investigations completed but had evidence quality problems: one combined a historical state-change timestamp with a later device-value observation; another attributed a light OFF to an inactive-motion rule despite an observed ~1-second gap against a currently configured 15-second delay. These are general event-attribution failures, not grounds for device-specific patches.

The same tests each reported `hub_device_monitor.configured=true` and `offered_to_model=true`, but their recorded `tool_calls` contained **no** `homebrain_read_device_monitor` calls. Native `hub_list_device_events` is Hubitat event history, not the separate Monitor archive. An offered source is not proven reachable or used. Whether the standalone installed Monitor was actively collecting and which devices it had selected cannot be established from these captures.

## Improvement without added model or hub load

- The existing tool-free **final claim audit** now explicitly requires a historical claim's full date+time+attribute+value to match ONE original source event row. It must sort returned events by timestamps before narrating, distinguish current state from historical events, and never combine timestamp/value from different events.
- When an answer proposes a configuration-dependent delay/threshold cause, compare observed event intervals against the configured requirement. An observed shorter gap contradicts that exact hypothetical trigger+delay explanation unless the original returned receipts independently establish a prior start/other path. Do not invent one to rescue a favored cause. Keep historical settings, unverified co-sensors and competing issuers unknown where necessary.
- A **bounded temporal source navigation aid** is built on demand from previously returned successful native event receipts and the existing final draft's cited clocks: exact same-clock matches and nearby **nonmatching** returned rows with safe event names and small typed values. This is navigation, not a source or proof of absence. Raw logs, event descriptions, listener text, credentials and large uncontrolled data are excluded. No new compulsory model pass, tool discovery, background polling, source read, retry, write or provider switch.
- PRIVATE Technical JSON now exposes `read_source_usage`: successful native device-event reads; Monitor tool attempts; successful Monitor status/history or compare reads; and whether the separate Monitor's saved history was actually used. The counters are computed from existing in-request receipts, not assumed from configuration.

## Synthetic regression and acceptance

Synthetic tests cover mixed timestamp/value sources, nonmatching quoted clocks, event-order prompts, configured-delay contradiction guard, bounded events/quoted clocks, sensitive event field exclusion, no mutation of raw receipts and Monitor offered-versus-used states. Synthetic tests do not verify the quality of the actual cloud model nor provide hub stability guarantees.

**Release gate:** complete V2 Python, container, metadata, screenshot and source-contract CI, then successful merge build.

**Live acceptance:** after verifying hub stability, make one new read-only causal request, retain the PRIVATE original MCP receipts and compare the pre-audit draft to final answer. The factual requirement is no spliced event timestamp/value or unsupported definite controller cause. Also verify `read_source_usage.hub_device_monitor_history_used`: it should be **false** until the model actually chooses a successful `homebrain_read_device_monitor` history/compare tool call. The separate Monitor stores selected-device binned measurements and is not interchangeable with full native event logs or guaranteed precise transition timestamps. Explicit user-triggered Monitor status can verify connectivity but is not part of ordinary background polling.
