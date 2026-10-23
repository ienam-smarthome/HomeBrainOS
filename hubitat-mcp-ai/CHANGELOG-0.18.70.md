# HomeBrainOS v0.18.70 — Live existing-rule audit routing corrections

## Live regression — 23 October 2026

After installation of v0.18.69, tests attempting to verify installed Rule Machine app **4246** returned `comprehensive-system-audit` and `rule_design_review` instead of the intended `existing_rule_verification`. One full System Check investigated 205 devices without reading app 4246. Another route read app 4246 health/config but appended a prospective *native rule creation feasibility gate* despite the rule already existing. Both responses were read-only.

## Root causes and bounds

- `targeted_rule_scope_policy._FUTURE_RULE_PROPOSAL` treated the explicitly **negated** phrase "Do not propose a new rule" as positive future-rule intent, preventing `existing_rule_verification`.
- A simple installed-rule status request could also be classified as `rule_design_review`, since the original conservative no-write classifier was used for *presentation* without requiring affirmative new-rule intent.
- `adaptive_investigation_policy.source_evidence_request` treated "show the actual source evidence" as a request for raw Groovy source implementation. As a result, unrelated `source_code` completion obligations could override an existing rule/configuration question.
- Exhaustive **exact-name duplicate checks** can use "audit all rules with the same name"; the broad-scope matcher should not read that as authority for a hub-wide audit. We do not know the exact prompt used for the first live System Check, so its full causal chain remains to be independently confirmed.

## Corrections

- Treat negated new-rule proposal phrases as prohibitions, not as user intent to design a new automation.
- Apply future-design prose calibration only to actual prospective designs; preserve the existing strict no-write checks for all read-only requests.
- Preserve named, exact-name duplicate searches as targeted rule audits, while still routing genuine all-hub audits to System Check.
- Exclude generic "actual source evidence" reporting language from Groovy implementation source-reading requirements.
- Add regression tests for the v0.18.69 Test 1 phrasing, exact-name searches, simple status, real future-rule proposals, whole-hub audits and source-reading classification.

## Scope and limitations

This change does **not** read or mutate live Hubitat configuration, touch apps 4246/4019, verify nighttime execution, or implement new typed Rule Machine configuration evidence extraction. Missing or generic app-config receipts remain insufficient to verify ordered actions and conditions. Review GitHub Actions before merging or deploying.
