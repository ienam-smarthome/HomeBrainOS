# HomeBrainOS v0.18.65 — Native Rule Machine subtype syntax and bounded night-idle validation

## Live failure from the user's v0.18.64 active-rule request
The latest 2026-10-22 write attempt for `Livingroom Light 1 – Night Idle OFF – TEST` (switch 7805, FP400 7978, 23:00–06:00, uninterrupted 10-minute motion inactivity) reached native RM tool-guide discovery and checked current devices and existing Rule Machine inventory. It made 10 read-only calls, 8 free Gemma rounds and ended in **failed** proposal validation after ~77.6 seconds, no confirmation and no hub write.

The generated `addActions` used invalid wrapper maps `{"ifThen":{...}}`, `{"delay":{...}}`, `{"cancelDelay":{}}`, `{"endIf":{}}` where the upstream native `hub_set_rule` addAction contract requires **flat explicit** `{"capability":"ifThen","expression":...}`, `{"capability":"delay","minutes":10,"cancelable":true}`, `{"capability":"cancelDelay"}` and `{"capability":"endIf"}`. The last IF incorrectly mixed `Certain Time (and optional date)`, which is a trigger capability, into an expression. Even mechanically fixing syntax would not establish a safe 10-minute delay.

The failure reply echoed the **entire rejected payload**, including user-specific rule/device IDs and an upstream guide best-practice key. That was unnecessary; only a sanitized validator reason is needed.

## Fix
- Extend the existing deterministic `normalize_rule_machine_proposal` to rewrite only unambiguous **documented** single-key wrapper aliases into flat capability-tagged native action objects. The normalizer does not drop unknown fields, invent missing actions, alter the user's devices, or submit a write.
- Validate IF/ELSE/ENDIF balance, required expressions, clock-condition syntax, event-versus-condition misuse, and positive delay duration before confirmation.
- Preserve the multiple-daily-times safety policy but allow one **strictly bounded** program structure for a cross-midnight night-idle OFF design. It requires six source-confirmed triggers (motion active/inactive, switch on/off, entry and exit times), first action cancelDelay, matching pre-delay AND final AND guard on motion inactive + switch ON + Between two times, cancelable delay, OFF-only switch action, and closed IF blocks. All other multi-time/multi-action structures remain blocked.
- Explain required canonical action shapes to the model before write-proposal generation to reduce repeated guessing.
- Stop echoing raw rejected native gateway payloads (including guide tokens) in end-user replies. Provide precise validator reason instead.
- Preserve the existing mandatory **confirmation gate**, readback requirement, current device/duplicate-rule checks and no-write-until-approval policy. No Hubitat command was executed in this repository update.

## Scope and limits
This is **schema and static-control-flow validation**, not runtime proof that a Hubitat Rule Machine rule actually executes the intended behavior. It is not a general-purpose Rule Machine compiler and does not independently verify cancellation execution on the hub or eliminate app 4019's shorter inactive-OFF conflict. The model must use installed native discovery schemas and emit a valid proposal; the user must confirm before any write, with a readback and controlled testing afterward.

## Validation
Regression tests replay the rejected wrapper fields and invalid time IF, exercise one strictly matched seven-action night-idle program, and ensure unbalanced blocks, wrong device IDs, missing cancel triggers and unknown wrappers cannot silently pass. All CI workflows must pass before merge. Live retest required afterward.
