# HomeBrainOS v0.18.46 — Read-only investigation intent and Internet control grounding

## Live failure (v0.18.45)
A read-only request to investigate TV smart-plug 4221, Google TV/Internet control 6923, and feasibility of a cumulative one-hour usage budget ended as `request_class=write`, `outcome=unresolved`, and the generic "I could not verify that this action actually ran" refusal after five Gemma rounds and eight **read-only** tool calls. No command was executed. The result contains `proposal_write_attempts_blocked=1`, indicating the model also attempted an unauthorized write in a proposal-only plan.

## Code-level cause and correction
- In `_explicit_mutation_request`, the secondary mutation matcher treated the trailing negative instruction "Do not create rules **or change device states**" (and similar "and change") as an independent positive write. This sets the mutation-authorisation flag for the whole read-only prompt, which triggers the `_unverified_mutation_guard` fallback and discards real read-only findings.
- The policy now removes an explicitly negated action clause *only for intent classification*, stopping at independent imperative transitions or sentence boundaries. A later real "but block Internet" or "Then block" still requires write authorisation and confirmation. No changes to action execution or its confirmation gate.
- The model-visible `homebrain_resolve_device` description still instructed the model to require literal `blockInternet/allowInternet` commands, contradicting the established authoritative **Internet**-room Switch convention (`off=blocked`, `on=allowed`). Update the tool's description to require Internet room membership, exact target identity, and real supported Switch commands. This avoids the repeated failed capability-constrained lookup.

## Tests
- Replay the live TV cumulative-usage *read-only investigation* and classify it as `live-read` without suppressing successful read evidence.
- Prohibitions: "Do not turn it off", "Never disable", "Do not create or change".
- Preserve genuinely separate write requests: "and change", "but block", "Then block" and post-prohibition "instead block".
- Verify the current tool guidance describes Internet-room actual commands.

## Boundaries
This does not create or enable TV usage automation. An actual implementation must independently verify TV activity against power-meter values, handle cumulative state across restarts, use exact IDs and supported Hubitat commands, and reset only on a verified change of the authoritative access-control switch. A read-only recommendation must never trigger any Hubitat mutation. The CI and live Hubitat tests are separate: passing unit tests does not verify current device states.

Merge only after all three CI workflows succeed.
