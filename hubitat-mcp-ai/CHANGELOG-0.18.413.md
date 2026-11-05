# HomeBrainOS 0.18.413 — preserve source-scoped native dated-trigger answers

## Installed v0.18.412 acceptance, 5 November 2026

The user reran the prior existing native Rule Machine dated-trigger read-only request. The **scanner succeeded**, but the final *answer* was replaced by the generic existing-rule verification report.

- 4.671 seconds total, zero Gemma/provider rounds, 13 read-only external MCP source calls, 1 local typed projection.
- Native Rule-5.1 child inventory returned 42 visible candidate rules in one complete returned page.
- The scanner inspected 12 exact rule IDs: 1881, 2075, 2084, 2217, 2305, 2706, 2710, 2817, 2843, 2844, 2967, 3055. Of those, 11 typed native reads were verified; rule 2967 was unreadable/incomplete. 30 visible candidate IDs remained beyond the bounded first batch.
- Rule 2710 returned a native trigger-row 1 with `time1` type enum and value "A specific time", `atTime1` type time and value "22:30", `date1` type bool with **no verified boolean value**, and no returned `atDate1`. This does **not** establish an enabled dated trigger, date stored or actual execution.
- The local `typed_native_dated_trigger_discovery` receipt correctly reported `savedDatedFieldReadbackVerified=false`, `moreCandidatesMayExist=true`, `absenceProven=false`, `readinessForMutation=false`, with `investigation_coverage.domain=native_dated_trigger_discovery`.
- Despite that valid typed coverage, the visible answer was the unrelated "Read-only existing-rule verification" template, claiming stored-action-tree, duplicate-rule, inactivity-OFF and controller limitations. No modifying Hubitat calls were recorded.

## Root cause and narrow fix

The `process_user_request_result` **pre-shared-completion** stage still calculated a broad `existing_rule_verification` contract from the text and applied `calibrate_existing_rule_verification()` before the later typed `native_dated_trigger_discovery` completion. That earlier calibrator *replaced the specialist scanner's message*, even though final Technical JSON coverage had been corrected.

- Recognize a same-turn typed `homebrain_native_dated_trigger_discovery` receipt in the original agent result publication and preserve the specialist coverage/answer *before* the generic rule audit calibrator. Source receipt is necessary: prompt keywords alone never exempt unrelated answers from the existing rule safety guard.
- Add a second receipt-attested no-overwrite guard within the existing-rule calibrator for future caller paths. Without the specialist receipt, generic rule claims remain subject to normal evidence calibration.
- Publish bounded partial native time/date observations when a scan finds some relevant fields but no complete enabled date; do not hide valuable `atTime`, date toggle or missing `atDate` facts.
- Distinguish a successfully inspected native trigger/settings document from a *verified enabled dated trigger*. Avoid describing an empty/non-dated native read as a "persisted dated-field read verified".
- Preserve a bounded no-match and actual scan offset. A first-batch no-match is not proof that no installed dated rule exists.

No additional MCP calls or model rounds; no form-opening operations, write tools, device control, backup/confirmation changes, native writer privileges, or >=5.1.6 authoring-version change.

## Regression and next installed acceptance

Tests reproduce the *actual* 42-candidate/12-rule/one-unverified-read shape including the partial rule 2710 fields. They assert the earlier generic calibrator and final shared completion retain the source-scoped dated scanner answer; source-dependent exceptions cannot disable the generic guard for unrelated existing-rule audits or when the typed scan receipt is absent.

After installing 0.18.413, rerun the same read-only existing dated-trigger request. Expect the visible native scan message with 42 candidates, 12 inspected IDs, rule 2710 partial field details and **next scan offset 12**, alongside `native_dated_trigger_discovery` coverage. If further sampling is desired, explicitly continue from offset 12. This release does not claim an existing enabled dated rule or authorise one to be created.
