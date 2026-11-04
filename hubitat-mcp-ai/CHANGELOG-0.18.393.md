# HomeBrainOS v0.18.393 — exact named-rule read routing

## Live failure

Installed v0.18.392, prompt to read the existing Rule Machine rule named "One-off block TV", produced a 0.7-second global `automation-status` reply listing 165 automation entries instead of reading the requested native rule document. The submitted trace shows only `hub_list_apps` and `hub_list_rules`; no `hub_set_rule(operation=read)` occurred. That was a routing miss, not a native document access failure.

## Fix

- Exact quoted `rule named/called/titled "X"` inspection prompts bypass inventory/status matching, even when the question also mentions scheduled job status, health or a rule ID.
- The host resolves an exact unique name against a **complete** source-returned `hub_list_rules` inventory and calls the existing privacy-bounded native rule document reader with `operation=read`. No editor forms, execution, mutation or confirmation are requested.
- Missing/duplicate names, incomplete lists, unavailable native gateway or failed native document reads are stated explicitly. Unverified actions are not invented. This is a generic capability, not a hardcoded Google TV/rule ID patch.
- Existing explicit all-automation listing remains unchanged.

## Verification

Synthetic read-only tests cover the original quoted request, exact match/duplicate/no-match, native read shape and failure calibration. CI and link to PR provide engineering results. Real v0.18.393 same-question first answer and native read coverage, runtime executions and quality impact **NOT MEASURED** pending installation and a fresh read-only test.

## Safety and rollback

Only read-only routing/source materialisation changes; no live Hubitat/HA/Internet or rule changes. A source mismatch fails closed. Revert this release if named-rule details regress; `0.18.392` remains the previous stable automation-status presentation.
