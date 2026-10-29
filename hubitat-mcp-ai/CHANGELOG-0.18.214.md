# Hubitat MCP AI v0.18.214 — Source-connected general investigations

## Live investigation, 29 October 2026

The v0.18.213 general health prompt returned 8 successful MCP reads in 33.416 seconds (versus the prior 38.475-second *different run*); the model finished before a final synthesis, giving `final_synthesis_ms=0` and no rejected operations. It independently retrieved:
- A health sample of 51 stale and 1 unknown-activity devices, but stale is not independently proven offline.
- 28 Bedroom 3 Mesh watchdog WARN rows, and device 7103 reporting `healthStatus=offline`, `deviceHealth=stale`, a lastSeen value from 12 October, while `mqttStatus=connected` describes the hub's MQTT client rather than necessarily the plug.
- 10 Matter Zemismart M1 Bridge WARN rows, and device 7776 reporting `networkStatus=offline` **and** `healthStatus=online`, separate source attributes that require distinguishing rather than ignoring either.
- 37 combined SenseCap D1 Settings WARN rows (HTTP 408 and host-unreachable sources), without independent source verification of whether this system is intentionally unpowered.
- Repeated Bedroom 2 TRV unprocessed-command WARNs; device 5309 still source-reported online and battery 95%.
- A source-reported Hubitat free-memory snapshot; no physical fault attributed.

Despite this, the *user-facing* answer ordered a generic health count, unknown activity, historical stale entries and a single `healthStatus=online` metric. V2's prior brief sorted by **claim kind**, not evidence strength, and `host_factual_brief_ready=false` because the model had naturally finished. It therefore showed the full claim list rather than the strongest related-source evidence.

## Architectural change

- New `native_cross_source_brief.py` builds a **bounded source-identity evidence graph** from independent successful MCP read receipts. WARN/ERROR groups are attached to a later `hub_get_device` response only when the source-provided ID and independently authorised target filter match. It supports generic source IDs and read types; it does not route or prefer named devices, particular phrases or fixed room identifiers.
- Source evidence triage uses observed error/warning recurrence and independent current-state corroboration, with explicit attention to source-reported `healthStatus`, `networkStatus`, `deviceHealth`, `mqttStatus`, last-seen and source age. These fields are shown separately, never conflated as network proof. Only allowlisted, bounded projected fields are presented. No raw source code, credentials, untrusted log text or user-provided advice can become verified prose.
- When a genuinely source-connected case exists, the main V2 `answer.text` leads with a few bounded, directly attributable observations and read IDs **even when the model finished naturally**. Full claim validation, returned read windows, gaps and failures remain in `report.text`.
- The reported order is an **evidence-for-triage heuristic**, not independently verified fault severity or causal attribution; no physical failure, app activity or automation breakage is inferred from warning counts alone.
- Add diagnostics for case/connected-source counts and a distinct concise-answer source, plus 6 tests for multiple unrelated source identities, cross-source attribution, conflicting status fields, bogus IDs, unsafe telemetry, app-only errors and the full model-finished agent case.

## Remaining work

This improves *retrieval-to-answer coherence* and source corroboration across arbitrary device IDs, but does not yet deliver full Claude-style open-ended natural-language analysis or prove V2 is better than V1. The next milestone is **model-authored concise explanation under independent atomic claim validation**, with paired V1/V2 live tests across unrelated task types. Historical log windows remain capped and a performance/correctness comparison requires identical questions against both engines.

No write permissions, device controls, automations or Main Ask behaviour are changed. Native V2 remains read-only.
