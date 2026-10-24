# HomeBrainOS 0.18.107 — Spoken individual light names and safe investigative routing

## Live regression (24 October 2026)

A straightforward user command, **"turn on living room light two"**, was classified as a sensitive room/group control and failed after 25.1 seconds (including 24.8 seconds of MCP HTTP). It said "I could not verify the exact device list ... Nothing was sent", but the result incorrectly showed **Success**. This was not a read-only user request: the user plainly intended to turn on one light. The previously reported read-only investigation of Livingroom Light 1 exhibited a separate, related bug: the general semantic control eligibility predicate allowed non-command narrative text to enter the write-only device target resolver.

## Changes

- **Spoken device identity binding:** Canonicalise spoken "living room" and the fused device label "Livingroom" consistently, and convert "two" to "2". The pre-existing longest-match, exact-unique-entity grounder now binds the complete spoken "living room light two" to the single device **Livingroom Light 2**, ahead of the containing Living Room and the nearby Light 1. This is entity normalization, not a keyword-to-tool route.
- **Actual command boundary:** Only command-shaped sentences can enter the semantic immediate-control path. The previous predicate treated any unqualified sentence as a potential actuator request, allowing a historical explanation to be mis-planned as a sensitive room command.
- **Explicit read-only veto:** User instructions such as "Read-only; do not modify anything" categorically block both immediate control eligibility and independent host-side mutation authorisation, even if ON/OFF and command history words appear in the investigation.
- **Outcome integrity:** When a proposed sensitive command cannot resolve the exact supported device identities, increment the existing device_resolution_missing counter so HomeBrain reports **Unresolved**, never **Success** with no operation.
- **Replay tests:** Cover the actual spoken-command phrase with two sibling lights and a containing room; single target commands without model or group approval; plural "living room lights" still stages bulk confirmation; read-only investigation remains with the model; normal level/thermostat actions remain eligible. All tests use mock MCP, not the live hub.

## Limitations

This is a targeted safety/identity correction, not evidence that every accent, device alias or generic historical investigation is already handled. It does not change real Hubitat switches, rules or model budget. Test the live direct ON for Livingroom Light 2 only after the add-on is updated and verified.
