# HomeBrainOS v0.18.71 — Evidence-first existing-rule verdicts

## Live regression (23 October 2026)
Version 0.18.70 correctly routed a targeted read-only investigation of existing Rule Machine app **4246** and comparison app **4019** to `existing_rule_verification`. Yet the response retained the heading **"Read-only rule design review"** and claimed a verified six-trigger/seven-action structure, a 10-minute cancelable delay, no exact-name duplicates, a 30-second controller OFF setting and an active 208-minute lockout. The retained evidence did not contain supporting typed trigger/action/duplicate/settings values. The API coverage correctly said `stored_logic=checked-unverified` and `duplicates=checked-unverified`.

## Verified source cause
The final review banner in `mcp_agent_orchestrator.py` still used the broad no-write rule-design classifier rather than the new scoped prospective-rule classifier. The model's narrative could also pass through despite a partial typed evidence coverage verdict.

## Fix
- Use `is_new_rule_design_review_request` to select the future-design banner, while retaining the existing no-write safety check and confirmation path.
- On `existing_rule_verification`, when stored logic remains unverified, produce a host-assembled partial report from the typed rule-health and local-variable receipts rather than displaying unsupported model claims as established facts.
- Distinguish proved stopped/broken fields from active/enabled status, and identify that generic app page receipts do not certify delay values, exact action trees or duplicate absence.
- Only retain full model synthesis when the existing evidence contract has a validated typed semantic action-tree receipt.
- Add regressions for the actual app 4246/4019 receipt set, unsupported duplicate/count/delay claims, and preserved fully typed decisions.

## Limitations
This release does **not** invent a typed persisted-rule action extractor or obtain actual 4019 configuration values. The app 4246 trigger/action structure, effective lockout/idle delays and nighttime runtime remain unverified until independent typed evidence is returned.

No Hubitat rules, apps or devices are modified by this change.
