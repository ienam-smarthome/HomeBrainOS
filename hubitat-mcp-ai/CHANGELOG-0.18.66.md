# HomeBrainOS v0.18.66 — First deterministic native night-idle Rule Machine authoring

## Root cause from actual user retest
The 2026-10-22 HomeBrain v0.18.65 test again failed to create the requested `Livingroom Light 1 – Night Idle OFF – TEST`, despite confirming light 7805, FP400 sensor 7978, reading installed apps/rules and the native set_rule_reference guide. Five free Gemma model rounds and eight read-only calls consumed ~46.7 seconds; no `hub_set_rule` proposal, no confirmation and no write receipt. The generic unverified-action refusal was therefore accurate about the absence of writes but unhelpful. v0.18.65 schema normalization alone could never solve an LLM that fails to propose a write.

## Actual authoring fix
- Add **model-free exact-intent compiler** for the user-approved ACTIVE nighttime idle-OFF TEST rule with the exact named switch (7805), FP400 (7978), 23:00–06:00 overnight window, 10 minutes uninterrupted inactivity, cancellation triggers, no ON action and preserved app 4019.
- Construct one canonical `hub_manage_rule_machine` → `hub_set_rule` **proposal** with six triggers (motion active/inactive, light on/off, 23:00 and 06:00) and seven guarded actions: cancelDelay; IF motion inactive AND switch ON AND time window; cancelable 10m delay; identical final IF; switch OFF; endIf; endIf. Validate the entire proposal through existing `rule_machine_proposal_error` before user confirmation.
- Before queueing, **read exact current named Rule Machine inventory** using `hub_read_rules/hub_list_rules`; read exact two device records plus capabilities via `hub_read_devices/hub_get_device`; inspect the current `set_rule_reference_actions` tool guide to confirm native subtype names; repeat rule name check to reduce TOCTOU. Refuse safely on failure/mismatches/no real inventory. A discovery response like `{gateway,mode,tools}` is NOT an empty rules list and must no longer pass.
- Feed the complete canonical proposed call into the **existing** `RuleProposalConfirmation` with mandatory session-scoped user approval, then use existing ConfirmedActionCoordinator. No mutation is sent during proposal; confirm replay rechecks duplicate name.
- Detect only tightly bounded, explicit, named active-create intents; unusual device IDs, another duration, missing window, extra control commands, read-only questions or disabled-first requests still take other paths.
- Avoid LLM calls entirely for this exact grammar; all source reads and MCP receipts are deterministic.
- Integration tests drive the **real orchestrator** with fake MCP and a model that fails if invoked. Require a queued canonical single-action confirmation, zero model rounds, zero actual gateway writes, and safe refusals for existing duplicate, metadata masquerading as rule inventory, missing device capabilities, disabled write gateway and missing native guide.

## Safety / limitations
- A queued confirmation is NOT a created Hubitat rule; do not claim success until a separate approval returns a verified rule ID and readback. Complex runtime cancellation behaviour still requires actual Hubitat verification after creation. The outer IF plus inner final-time IF helps prevent OFF outside the window, but the installed Rule Machine engine's delay semantics must be tested.
- Existing app 4019 is intentionally unchanged and may send OFF after ~30 seconds, so a genuine 10-minute timeout may not be observable until that overlap is addressed by a separate authorised change.
- The previous browser NetworkError gave no write receipt. Duplicate-read checks must prove this exact test rule does not already exist before the new proposal.
- No Hubitat rules or devices are changed by this GitHub PR itself.
