# HomeBrainOS 0.18.99 — AI-led source follow-through for unresolved device incidents

## Live evidence (2026-10-24)

In HomeBrainOS 0.18.98 the read-only Bedroom 3 Mesh incident correctly retained a mathematically corroborated watchdog-reference-to-MQTT-disconnect timing clue (~19:48:37, 23 October). It found the device's dependency list and checked a 24-hour app log window for app 3999 (zero returned entries). Yet it did not read any controlling automation configuration or installed driver source. The response used nine free model rounds (~62 seconds model time), eight tool calls, and finished unresolved after ~68 seconds.

The absence of log entries for an app is not evidence that the app controls the device or that it never executed. A successful dependency lookup is a useful lead, not the conclusion to that lead.

## Changes

- Preserve the request-scoped AI interpretation as the only driver of a connectivity diagnosis. Add a concise initial read-only evidence roadmap so the model can prioritise the actual target device, its reported versus physical MQTT/telemetry clocks, source-relevant watchdog timestamp writes/reads, and the actual dependent automation settings without repeated tool discovery or whole-hub inventories.
- Explicitly enable read-only investigation tool selection for short connectivity/root-cause questions as well as verbose investigations. The host's independent mutation classifier and read/write gates remain unchanged.
- After a baseline and the existing single incident-depth follow-up, permit at most **one** additional AI-selected read-only evidence follow-through when a successful, target-ID-scoped dependency lookup has occurred yet the stored app configuration and/or driver source have not been read. The host identifies missing *evidence classes*; the AI chooses the registered tool, scope and whether further reads are possible. Never invent a tool, perform a mutation, or repeat an unavailable source.
- The extra follow-through is progress-gated, uses the existing tool/round budgets, and is omitted if no model round remains. It cannot activate on a plain status request, missing target ID, a multi-device read, or an unrelated/failed/mutating dependency receipt.
- Distinguish empty app-log reads from confirmed execution evidence. Surface checked-empty scoped app IDs as bounded observations, not proof the owning automation did not execute.

## Direct factual answer presentation

- A short question such as "How long has the TV been on today?" is answered from the single verified target's timed switch history rather than being reclassified as an initiating-command investigation or padded with a "Competing explanations" report.
- The duration summary distinguishes paired observed daytime ON/OFF intervals from a separately inferred midnight carry-over. In the live October 24 case the prior-day ON (22:27:37) and first OFF (00:12:54) imply ~13 minutes after midnight, which can be reported as an estimate alongside 1h46m across three later sessions (approx. 1h59m total). It never treats uncertain event-stream integrity as an exact physical continuity claim.
- Model-proposed hypotheses remain in structured metadata, but the final answer automatically renders a competing-explanations list only when the user explicitly requests a comparison of possibilities.

## Safety and limitations

All changes are to the HomeBrainOS repository. No live Hubitat device, app, rule or automation configuration is changed. The existing total investigation deadline still bounds long model responses; this patch does not establish the physical cause of device 7103 or guarantee a particular registered MCP tool exists. Test with a fresh read-only question after upgrade and inspect whether targeted app configuration or mapped driver source was actually fetched.
