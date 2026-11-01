# v0.18.326 — Stage 9.1 mobile copy test results

## User-visible improvement
- Add **Copy command results** next to the Command Shadow report, enabled after the bounded read completes (including error results).
- Add **Copy test results** next to the Stage 9.1 issuing-app follow-up; it combines the existing Command Shadow report and the app-decision follow-up in one easy-to-paste text block for mobile ChatGPT.
- Buttons start disabled and cannot copy stale Stage 9.1 follow-up text after a new Command Shadow comparison begins. During a new read, the corresponding copy control is disabled.
- Use the existing clipboard compatibility helper for Android browsers and Home Assistant ingress: confirmation on successful copy and a blocked-copy message if the browser denies clipboard access.
- The copied text is the *already rendered, privacy-filtered result*, never private raw app-log messages or hidden backend metadata.

## Safety and scope
- Client-only UI change. No new Hubitat reads, app-log reads, Cloud calls, commands, production publisher changes or evidence-classification changes.
- All consent gates are unchanged. Copying requires no additional consent because it does not perform a source query.
- Smoke/regression assertions cover both report targets, stale-result reset, no fetch in the copy handler and safe displayed-text-only behavior.

## Manual acceptance
On an Android phone using Home Assistant ingress: run Live Shadow → Command Shadow → Compare command and switch events. Confirm **Copy command results** copies the full visible report. If the recent attributable OFF command exposes the Stage 9.1 follow-up, run it with separate consent and select **Copy test results**. Paste into ChatGPT and verify both the command report and classified app-decision result are included. Re-run Command Shadow and ensure the previous app-decision copy is disabled until a new follow-up completes. If clipboard permission is denied, use the displayed report text as a fallback.

Rollback: revert this PR to v0.18.325.
