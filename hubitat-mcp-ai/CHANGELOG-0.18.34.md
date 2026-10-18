# v0.18.34 — Keep historical explanations on the requested device

## Live input (18 October 2026, HomeBrain v0.18.33)
The Free Gemma request explicitly asked to **explain switch=off vs command-off vs app execution vs physical acknowledgement**, then state what evidence exists for **Bedroom 3 Mesh on 12 October 2026**. The resulting structured response was successfully classified as live-read, with 9 free Gemma rounds, 10 read tool calls, 31.1 seconds and `outcome=unresolved`. However:
- The model read the targeted Bedroom 3 Mesh device (7103), then a **broad 30-minute whole-hub log sample** unrelated to the 12 October boundary, saw Linptech Kitchen sensor entries, and tried to explain that device instead.
- The existing device-claim guard retried after seeing an unrelated device label. It ultimately emitted a refusal about **Linptech Kitchen sensor**, rather than answering the named user's question.
- It queried 20 then 50 **newest-first unfiltered** device events, dominated by current watchdog `deviceHealth` messages; the source indicated truncation/uncertain historical coverage. The required specific **`command-off`** stream was not checked.
- The v0.18.32 command-history completion planner only accepted `historical_rule_execution_request` and a **numeric device ID in the user's text**. This valid historical explanation used a verified device label instead, so the planner was not applicable.
- **No historical OFF issuer or physical acknowledgement is proved by the response**. Device OFF state is not a command.

## Architectural changes
- Add a generic, narrow source planner for **dated, device-named questions explicitly referencing `command-on` or `command-off`**. Resolve the unique numeric ID from an actual successful targeted lookup, then reuse an observed, bounded history lookback and issue **one** native filtered command-event read before synthesis. Do not widen general explanations, assume missing source history, invent target IDs, or retry failed command reads.
- Reject broad `hub_get_logs` requests in this verified, dated single-subject context when they have no device/app/source/pattern filter. This prevents unrelated recent diagnostics entering the causal evidence loop. Whole-hub audits remain unchanged.
- When an explanatory answer drifts to an **unrequested** device named in incidental tool output, use a deterministic **source-faithful partial answer** about the unique requested device rather than spending another model round investigating the irrelevant sensor. Explain all four evidence types and report only the observed target state, bounded event/command read attempts and remaining gaps. Do not claim specific app causality or physical ACK without supporting sources.
- Retain all existing user-authorized mutation confirmation paths and default Free routing. No Hubitat writes, no Claude calls, no automatic paid fallback.

## Validation
Tests use the real v0.18.33 question and observed receipt shapes: unique targeted device 7103, 168-hour newest-first event history, inferred switch attribute, noisy `deviceHealth`, `Linptech Kitchen sensor` contamination and source truncation. Cover command obligation and deduplication, ambiguous/unverified identities, safe log blocking, no changes to broad audit discovery, irrelevant-device fallback and non-overstatement of historical command/physical confirmation.

## Caution
The code-level path is ready for unit/CI validation, not proof of live Hubitat execution. The original separate historical **app 3950** investigation remains unverified. The requested 12 October boundary may no longer be present in retained history; an empty command query does **not** establish the command was never issued.

All three required CI workflows must pass before merge. Upgrade the add-on and run the identical Free Gemma explanation question, then the exact app3950/device7103 historical test. Inspect `evidence` for `hub_list_device_events(attribute=command-off)`; check `investigation_coverage` and model rounds.