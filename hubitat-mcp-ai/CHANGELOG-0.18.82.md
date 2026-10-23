# HomeBrainOS 0.18.82 — Scoped app routing and WARN-log evidence integrity

## Evidence: 23 October 2026, 0.18.81 read-only user tests

1. Comprehensive whole-hub audit completed a deterministic report in ~35.8 seconds, but the saved user preference `comprehensive_audit_ai_analysis_enabled=false` correctly disabled optional Gemma advisory. This release does not change or override that user-selected option.
2. A **targeted** comparison of app 4061, 3977 and 3933 incorrectly chose the `comprehensive-system-audit` route because the broad shortcut counted `Device` in the proper name `Device Status Report` plus `app` and `logs`. Thus it never answered the intended targeted question and did not run model reasoning with the saved audit toggle disabled.
3. A separate Gemma investigation (~57.7 seconds) sensibly rejected the hypothesis that disabling Life360 necessarily fixes all three apps, but claimed there were **no execution-time warnings for Octopus app 3933**. Its successful, scoped `hub_get_logs(appId=3933)` receipt held WARN entries for `scheduledLiveHeartbeat`, `childPollNow` and `scheduledYesterdayCheck` with durations from 137,116 to 478,707 ms around 19:56–19:59 (source clocks with unverified timezone).

## Changes

- Exclude a bounded cohort of 2–8 explicitly named app IDs from the generic whole-hub audit classifier unless the user explicitly asks for a system-wide audit. Leave explicit full audits on the existing dedicated audit route.
- Add deterministic final serializer check for **contradicted model absence statements** about long-running method warnings. The checker uses only successful structured current-turn `hub_get_logs` WARN/ERROR rows, exact originating app ID and numeric method-duration observations. It does not infer root causes, shared CPU load, connectivity or restarts.
- Repair the wrong `Not observed in provided logs` table cell or a false unqualified denial, preserving true negatives for unrelated apps or explicit thresholds (such as no observed method run above 500,000ms).
- Mark actual repairs with `evidence_validation.observed_long_method_denial_corrected=true`; no flag when no correction was needed.
- Add read-only replay tests for both user-observed regressions and register the runtime module.

## Known limitations / next tests

These checks repair misleading conclusions but do not demonstrate general Claude-equivalent reasoning. The user must deliberately save `comprehensive_audit_ai_analysis_enabled=true` to test the optional Gemma comprehensive audit. Method duration warnings across different apps can be correlated by reported source timestamps, but synchronous method completion time and aggregate percentages are not proof of a common fault or whole-hub CPU utilisation. No change to Hubitat, add-on saved options, confirmations or paid routing.
