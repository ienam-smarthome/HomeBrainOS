# HomeBrainOS v0.18.69 — Correct existing-rule verification routing and evidence scope

## Live regression, 22 October 2026
A read-only request to inspect the already-created Rule Machine app **4246** ("Livingroom Light 1 – Night Idle OFF – TEST") and compare app **4019** was presented as a *new-rule design review*. The model response repeated the new-rule feasibility gate even though native creation had already succeeded. The investigation coverage requested future rule compiler capabilities and did not establish the persisted action tree.

## Code-level cause
`RuleAuthoringService.is_read_only_rule_design_request()` intentionally detects rule + review/read-only + no-write instructions to prevent unconfirmed creation. That conservative classifier also matches existing-rule verification requests. `plan_investigation()` previously assigned this combination to `rule_design_review` before checking installed-rule scope, while the orchestrator reused the classifier for proposal-only prompts and final answer calibration. The no-write safety classifier itself must remain conservative.

## Fix
- Introduce a narrowly scoped `is_existing_rule_verification_request` classifier for explicitly named installed app IDs and requested rule details. Future-rule creation proposals that cite an existing controller remain in the proposal-only path.
- Give installed-rule verification a dedicated read-only investigation plan and actual-configuration evidence requirements. A generic `hub_get_app_config` response-field receipt marks the action tree *checked but unverified*, not complete.
- Preserve typed native rule-health evidence. Only explicitly validated, target-matched semantic receipts can verify the ordered action/trigger tree; a successful configuration read cannot.
- Exclude existing-rule inspections from proposed-new-rule prompting and feasibility caveats. Existing no-write and confirmation checks remain unchanged.
- Add regression tests for app 4246, comparison app 4019, future proposals, synthetic typed evidence, generic receipt limitations and preserved whole-hub/historical classification.

## Safety and limitations
This is application source-code work only. It does not create, change or execute Hubitat apps or devices, reconcile the original native write timeout, prove app 4019's effective OFF duration, or demonstrate the ten-minute nighttime behaviour at runtime. A separate typed configuration projection may be required before `stored_logic` can reach `observed` in live evidence coverage. Review GitHub Actions and merge only after tests pass.
