# HomeBrainOS v0.18.61 — Coherent rule-design plan, not disclaimer-only

## Live v0.18.60 regression
The 2026-10-22 HomeBrain vs Claude test reached `rule_design_review`, 7 read-only calls, 2 free Gemma4:31b rounds, ~16.5s. It identified a reported device ID/name mismatch (7764 is FP300 Toilet, not living-room) and retrieved app 4019. Its rule plan nevertheless said a `Wait for Event` timeout **ensures** 10 minutes continuous inactivity, that the Required Expression **prevents** any OFF outside 23:00–06:00, that OFF-only cannot affect the manual lockout, and that `hub_set_rule` can create the exact rule. A correct feasibility disclaimer was appended **after** the unsafe plan, leaving self-contradictory instructions.

The API correctly uses `rule_design_review` (v0.18.60 fix) but falsely emitted `sourceChecksComplete:true` because this future-rule task has an empty **historical** source-kind list, even while specific device/config/tool-capability evidence remained unverified.

## Correction
- Reconcile at the output boundary: when a verified combined native-rule schema is unavailable, replace the **entire unsafe Proposed Implementation Plan and Technical Feasibility sections**, not just selected unsupported phrases or an appended disclaimer. Keep the independent device and existing controller findings with a clear field-receipt provenance qualification.
- Render a **request-scoped requirements-level** design using only the user's requested window and inactive-duration. Include light-on-while-inactive, night-window opening, continuous inactivity, cancellation/retrigger requirements, final time/light/motion/duration guard, and existing competing controller. This is never represented as executable `hub_set_rule` JSON or verified Rule Machine action syntax.
- Clarify that a generic MCP success receipt listing response fields does **not** independently prove the model's named device room, persisted 30s OFF delay, complete Rule Machine action structure or lockout trigger. Verification of actual typed semantic values remains outstanding.
- Make `sourceChecksComplete` false for an incomplete design contract, and historical-kind `sourceKindsChecked` not applicable rather than vacuously true.
- Keep no-write/no-queue behaviour unchanged and do not add any new MCP calls, model rounds or unsupported compiler operations.

## Acceptance
Regression fixtures mirror the v0.18.60 contradictory answer and require no remaining misleading executable IF/WAIT/OFF or combined-authoring assertions, a single coherent design, correct overnight edge cases, source qualification, no false green completion indicator, and idempotence. All GitHub CI workflows required before merge; live add-on verification afterwards.

## Future architecture
Retrieve sanitized typed current-device labels/room/capabilities, persisted app 4019 logic and native Rule Machine guide/schema, then explicitly validate each proposed action/trigger/time condition and support real proposal compilation. Current release is solely evidence/safety consistency.
