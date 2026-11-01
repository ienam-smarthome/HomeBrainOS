# v0.18.327 — Stage 9.2 multi-command app-decision selection

## Live motivation
Hallway Light 1 (7829) on 1 November 2026 returned 11 source-attributed OFF commands by app 4012 and 11 switch-state reports in the bounded page. The prior Stage 9.1 interface showed its app-log follow-up only if exactly one attributable OFF command was present, so richer evidence incorrectly hid the follow-up.

## Fix
- Show a mobile-friendly **Recorded OFF command (UTC)** selector listing source-attributed, uniquely timestamped OFF command candidates in the existing bounded Command Shadow response.
- With multiple candidates, require an explicit selection (nothing is preselected). With a single candidate, preserve the prior selection behavior.
- Display the recorded issuer for orientation only. The browser sends solely the selected device ID, exact source UTC timestamp, and separate explicit consent; it cannot provide an app ID or change tool parameters.
- Backend continues to re-read the exact command row (one bounded device history read) before one strictly issuer-scoped four-minute diagnostic log read, both capped as in Stage 9.1.
- Reset the selector and clear prior follow-up results when starting a new Command Shadow comparison or changing selection. Keep the Stage 9.1 copy-test-results control.

## Provenance correction
- Mark the command device ID as explicitly verified only when the **selected exact-time OFF command's verified issuer** also has the matching explicit target device ID.
- An unrelated record from the same target and a different time, or a source row with an unverified producer, cannot elevate the selected command's identity proof.

## Safety
- Read-only, separate consent, 48-hour event horizon, no new Cloud calls or device controls; production publisher remains unchanged.
- Missing/ambiguous/expired records and log classifications retain fail-closed, evidence-bounded statuses.
- Tests cover multiple-candidate selection mechanics, no user-controlled app ID, privacy-safe copy, and identity-provenance edge cases.

## Phone acceptance
1. Update Hubitat MCP AI to v0.18.327.
2. Live Shadow → Command Shadow: device **7829**, UTC date **2026-11-01**; grant read-only consent and run.
3. In the Stage 9.2 follow-up, pick an OFF command, preferably **2026-11-01T14:35:05.894000+00:00** while within 48 hours.
4. Grant separate read-only app-log consent; run **Investigate recorded OFF command's app decisions**.
5. Tap **Copy test results** and paste into ChatGPT. Logs may be unavailable even if the issuer is verified.

Rollback: revert this PR to v0.18.326.
