# HomeBrain 0.17.86 — cross-domain investigative intent and provenance reliability

## Live regressions fixed
- A prompt beginning **“Choose a recent unexpected device state change...”** was misclassified as an explicit device selection. The parser handed the full task to a targeted labelFilter, generated three missing-resolution counters, and stopped with **zero AI rounds**. Device-selection fast paths now accept only short, explicit device names; open-ended selection/investigative instructions proceed to the main MCP tool-planning route. Genuine choices (“Choose the Hallway Light 1”, etc.) remain supported.
- A broad automation-fault audit with coordinated descriptors (“my broken or incomplete Hubitat automations”) missed the existing comprehensive System Check routing and only listed 38 rules without investigating faults. The automation-scope classifier now understands coordinated automation-state modifiers, while preserving targeted named-device causal inquiries.
- A live Bedroom 3 Mesh answer used a reported lastSeen date (12 October) and dataAgeSeconds (~45h) as if they agreed on 16 October, and inferred power from MQTT status. New independent metadata-clock reconciliation checks observedAt, lastSeen and reported age; contradictory values are disclosed before the answer, with a firm boundary between hub status and independently verified power/command reachability.

## Scope and limits
- All changes are **read-only evidence handling and routing**, not device or automation mutations.
- The comprehensive audit still depends on available Hubitat MCP health evidence; where individual logs, historical executions or rule-health operations are unavailable, the answer must say so.
- Date reconciliation currently accepts explicit BST/GMT UK-text lastSeen timestamps and valid timezone-aware ISO as-of times; other formats are not guessed.
- Selection delegation does not guarantee the model can select an incident from an unexposed journal. MCP capabilities and historical source coverage still govern what can be established.
- These are reliability fixes across three domains, not full implementation of a multi-hypothesis autonomous investigation planner.

## Verification
- Regression tests for open-ended selection vs named choices, broad vs targeted automation investigation, plausible and contradictory telemetry clocks, malformed timestamps and final API output.
- Full blocking Python and add-on test suite and container smoke validation required before merging.
