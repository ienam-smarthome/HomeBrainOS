# HomeBrainOS v2 alpha.79 — model-led installed-capability verification

**13 November 2026. Development-only. No Hubitat, network, device or native rule change.**

## Evidence-led reason for change

A PRIVATE installed alpha.78 first-answer capture asked whether the hub supported a truly single-time native rule and explicitly requested identity, capability and limitation verification. Three read-only native calls returned the server's rule-writing reference, an app **type** inventory, and a native rule inventory. No current typed **installed parent** record or exact dated-trigger field contract was read. The model nevertheless answered unconditionally that the installed system supported the requested one-time operation, mistaking a built-in type ID for an installed app instance and a datetime variable example for evidence of scheduled-trigger timing precision.

The source-sufficiency hook was **not invoked**, because the user's natural `Check whether ... Verify ...` wording fell outside the existing verification-intent qualifier. This is a general source-to-claim mismatch, not evidence that the server cannot create dated rules. The original private receipts are not published or copied into this repository.

## Narrow, reusable implementation

1. Preserve the existing model-led `source_verification` checkpoint. Recognise an explicit `Check whether` / `Check if` request **when it also contains proof/verification intent and a relevant status, capability, schema or identity subject**. Routine quick checks, ordinary commands, and questions without proof intent remain outside the expanded path. This chooses only the **opportunity for** one model review, not a tool, a cause, or a final answer.
2. Extend existing read-only evidence-review guidance with neutral evidence levels: advertised guide/schema; type/driver catalogue; typed installed instance; exact field/action contract; accepted configuration; observed execution. Do not equate type IDs and instance IDs, variable serialization formats and trigger precision, stored configuration and runtime execution.
3. Keep native form navigation outside read-only verification where the server warns that opening/rendering the form executes app code. No hardcoded rule tool, parent ID, device routing, action planner, automatic write, or forced read sequence.
4. Preserve the existing optional final claim audit after the model-led read-only review. Missing installed data yields a qualified result, not a fabricated positive or negative.

## Regression coverage

Synthetic fictional tests cover broad verification wording across controller, gateway and device domains; routine quick checks and writes that must not trigger the review; model-chosen additional typed native reads; no write gateway offered during the review; and model-authored final evidence calibration. Existing causal, historical, command approval, one-off timer, native rule and monitor contracts remain unchanged.

CI is a structural regression gate, not a claim that `gemma4:31b-cloud` will gather the right installed sources or correct the answer. No real Hubitat calls were made by this repository work.

## Source-real next step

Install and verify alpha.79 UI/API versions, then ask a **fresh read-only capability question** in normal Ask without prescribing exact MCP tool names. Preserve the first answer and PRIVATE original Technical JSON. Check that `source_review_invoked=true` and `source_review_kind=source_verification` where sufficient time remains; that any additional sources genuinely identify a current typed installed instance and exact capability contract; and that the answer distinguishes documented support from verified installed compatibility. If a safe read-only source cannot supply the exact dated-trigger schema, state the limitation without attempting native form navigation.

No hub-specific cleanup, new test rules or real writes are authorised. Existing one-off/permission safeguards remain as in alpha.78. After this focused acceptance, return to the **12 fresh read-only first answers across 6+ domains** under Gate B; do not count this explicitly coached diagnostic as a blind model-quality sample.
