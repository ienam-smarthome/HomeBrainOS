# Hubitat MCP AI v0.18.211 — General read-only AI intent boundary

## Live blocker from 29 October

The operator entered a valid read-only investigation in Native MCP mode ending `Read-only investigation; change nothing.` The V2 endpoint immediately returned `409 v2_control_not_supported`, displaying a device-control handoff without running the model or MCP. The production shared no-write parser matched `read-only` but then incorrectly interpreted the independent text `; change nothing` as a positive write because its regular expression checked only the verb, not the negative object. V2 reused a production command shortcut classifier as a prerequisite for all read-only questions.

## Cross-domain architecture change

- Add a shared **polarity-aware independent action clause** detector for negative objects (`change nothing`, `create no rules`, `turn no devices on`) and textual deliverables (`create a report`, `create a summary`). Distinguish a historical question's action words from a later independently affirmative imperative. This function never selects tools or grants write authority.
- Decouple opt-in V2 admission from the production fast-control routing function. V2 has a **negative-only** guard against direct requests to actuate/modify Hubitat state, including separately requested writes after an initial read. It does not classify or route general information tasks by terms in their content. The actual V2 MCP manifest, tool-effect, ID, field, and executor guards remain authoritative and READ-only even for unanticipated phrasings.
- Reinforce general-purpose objective interpretation for the Native READ model: the user's question could concern state, history, automations, system health, performance, energy, comparisons or app/rule behaviour, with no domain-specific forced route.
- V2 test panel explicitly invites general Hubitat questions, not just per-device investigations.
- Add cross-domain regression tests and a full authenticated HTTP replay of the **exact screenshot question**, asserting it reaches the model-facing Native READ entry without inventory or Hubitat mutations. Independent positive control requests still return HTTP 409 before model/MCP.
- Record staged general reasoning architecture and evaluation in `docs/architecture/V2-GENERAL-REASONING-ACCEPTANCE.md` so future development targets universal model-led reasoning, not one incident's vocabulary.

The normal Main Ask write permission, confirmation, and tool execution code is unchanged; the shared no-write helper now correctly handles negative clause polarity. This does NOT claim complete Claude-style answer quality or bring V2 into production. More general model reasoning/synthesis work is the next stage.
