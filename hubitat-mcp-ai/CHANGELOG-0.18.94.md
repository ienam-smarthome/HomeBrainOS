# HomeBrainOS 0.18.94 — Continue device root-cause investigations past baseline telemetry

## Replay: October 24 2026, version 0.18.93

The user's read-only Bedroom 3 Mesh (7103) investigation correctly reached `unified-mcp-agent` rather than System Check, taking 28.993 s (Gemma4:31b, five model rounds, five tool calls). It retrieved current device state, 14 device history events over a 24-hour bounded query and 45 matching logs, including repeated watchdog warnings. The evidence revealed materially inconsistent age counters:

- Saved `lastSeen = Mon Oct 12 01:30:01 BST 2026`: ~299.8 hours before current read.
- Saved `dataAgeSeconds = 162325`: ~45.1 hours.
- Watchdog reported `62838s without data`: ~17.45 hours at 13:15 local time.

The return values reflect **different clocks and/or differing code-path semantics**. They do not corroborate the last physical packet. More importantly, the model never inspected the installed Tasmota driver, the relevant power-saving automation configuration, or independent upstream network/broker telemetry. It still reached a stopping condition `causal_subject_empty_stop`, even though a missing ON/OFF active interval is irrelevant to diagnosing an offline/connected-status discrepancy.

## Architectural adjustment

- Introduce a **device incident evidence-depth checkpoint**. For a clearly scoped offline/MQTT/connectivity root-cause investigation, current attributes, one bounded event page, and device logs are baseline symptoms—not sufficient to support a root-cause verdict.
- If the model attempts to finish after that baseline, allow **one additional model-selected, read-only MCP tool opportunity** with concrete discriminating classes: installed driver code, relevant controlling automation configuration/execution, and independent physical/network/broker evidence where an actual registered read tool exists. These classes are not assumed available or already checked.
- Only the permitted MCP READ schemas are exposed. The model must verify code identity and automation target ownership, and may not guess a network gateway, use a write to test the plug, or claim upstream facts on Hubitat-only logs.
- The generic `causal_subject_empty_stop` based on *missing active switch interval* no longer short-circuits a device-offline root cause request; it remains intact for actual ON/OFF transition timeline investigations.
- Add an observability counter `device_incident_depth_retry` and replay tests based on the exact 0.18.93 read receipts, including negative tests for simple status questions, read failures and unrelated switch-transition requests.

This improves the model's opportunity to investigate like Claude but **does not certify** a physical root cause, network reachability, a particular driver source, ownership of Rule 3950, or guaranteed access to external broker tools. The user's actual Hubitat devices, rules, drivers, apps and settings remain unchanged. The selected free model path is unchanged.
