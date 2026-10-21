# HomeBrainOS v0.18.57 — Prefer verified Rule Machine candidates and avoid unrequested AI

## Why
The v0.18.56 live full-hub audit (2026-10-21) correctly retrieved six app pages but spent its sole RM settings pass on disabled Nest Mini rule 3951. It never selected the named lighting rules 3992/3931, although the normalized automation inventory already contains a reliable `type: "rule"` distinction from `hub_list_rules`. A tool-free optional advisory also timed out, making an otherwise deterministic audit slower.

## Fix
- Prioritize `type: "rule"` **only for selection**, along with recognized RM-5.x native types, before generic parent app IDs. It does not establish an RM version or action semantics.
- Maintain the strict Rule Machine 5.x type requirement for indexed-settings interpretation. The explicit current app-config type must identify RM 5.x before the `includeSettings:true` second pass. Do not override a definite different type.
- When more than two eligible RM configs exist, prioritize the *lighting comparison pair* over disabled-job candidates for the two bounded secondary settings reads. Disabled candidate app status and ordinary configuration still get their original reads.
- When a prompt qualifies for a comprehensive/cross-domain audit, use `comprehensive_audit_ai_analysis_enabled` (default false), not the broad-automation diagnosis setting (default true). Optional analysis remains available when specifically enabled.
- Keep existing six normal config-read cap, two concurrency, six-second dependency budget, no raw settings output and no inferred runtime rule conflict, action direction or callback owner.

## Verification
Regression tests exercise the v0.18.56 selection failure with normalized `rule` entries and mixed parent app IDs, two known RM 5.x lighting rules with distinct targets, rejection of unknown RM versions, correct `deviceId` dependent lookups and no automatic AI when comprehensive analysis is disabled. All three CI workflows must pass before merge.

## Still unresolved
Current Rule Machine settings maps reveal bounded typed device *references*, not complete conditions, action direction or historical execution. Scheduler owner IDs remain unverified. Live HA add-on retest is necessary.
