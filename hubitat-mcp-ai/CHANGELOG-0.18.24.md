# v0.18.24 — Historical cause must be supported by returned command evidence

## Live v0.18.23 finding

A strict-Paid DeepSeek investigation of Bedroom 3 Mesh (7103) ran for 410 seconds (8 DeepSeek rounds, 6 MCP tools, 403.8 seconds provider). Driver source ID 3686 was fully retrieved, device state/event history/log reads succeeded, and source method projection ran. A seven-day event-history request nonetheless exposed only a bounded, truncated set of recent Oct 17 events. The model asserted with high confidence that a named power-saving automation (app ID 3950) issued OFF at 01:30 Oct 12 and caused the offline transition, and simultaneously claimed driver source was not retrieved. Neither causal execution nor exact timeline is established by the returned receipts. The old completion reported success and objectiveSatisfied true.

## Evidence correction

- Add an **evidence-grounded named historical app-command guard** for source-led read-only investigations. A model claiming a named app ID issued a historic command must be corroborated by a returned, dated device command event produced by that same app. App configuration, broad hoursBack parameters, mere presence of an app name and truncated event pages are not substitutes for actual recorded execution.
- A relevant command event from a different date or different app does not prove the claimed historic action. Explicitly tentative statements ('unknown whether ...') are not rewritten into execution claims.
- When the final answer asserts an uncorroborated named-app execution, replace the unreliable causal narrative with a bounded, non-accusatory evidence summary. Preserve proof of checked code/device/history/log sources, disclose truncation, and explain that a missing event is **not** proof the app never ran.
- The source-coverage report now includes a separate `historicalCausalClaim` assessment, while `objectiveSatisfied`, `questionResolved`, `analysisAnswerVerified` and metrics remain unresolved/false for an unsupported causal verdict. API `success` is false for this false-verification condition.
- A simultaneous claim that driver source was not retrieved is flagged when the actual source receipt proves a successful read.

## Limitations

This is a narrow, high-precision guard for **asserted historic command causation attributed to named app IDs**, not a general proof engine for all natural-language causal claims. It does not establish if the Oct 12 command occurred, whether physical MQTT packets were received, or whether any Tasmota firmware/power problem existed. Date-bounded authoritative events, app logs, and broker/device evidence remain required for a verified root cause.

## Verification

New regression cases reproduce the Oct 17 bounded-history read and unsupported Oct 12 actor claim; verify actor/time mismatches, benign hypotheticals, prior app configuration not being execution proof, preserved source receipt, unsuccessful/unresolved outcome, and genuine current-turn matching command evidence. No device commands, permission changes, billing changes or ledger reset.
