# HomeBrainOS v0.18.192 — Actor/method priority and overlapping history deduplication

## Live regression (28 October 2026, v0.18.191)

The 22:48 Native V2 test took 27.465s. All 10 MCP reads executed successfully, but two additional hub_get_device proposals were locally rejected for missing required arguments. WARN history, 50 scoped device events and six app dependents substantiate app command issuers:

- App 4080 (00 Google Calendar Notifier): 13 sampled commands (5 setVolume, 8 speak) from 16:58–17:51; app 1679 (Adhan Player): 16 (including 11 refresh) from 17:00–18:15.
- Google Nest Hub device 7934: 43 returned runQ WARN rows during 17:04–17:58 (147,429 ms in a message), and later generic excessive-load WARN rows from 19:32–19:55. The first warnings overlap app commands; the latter generic group has no corresponding app command in the returned sample.
- The old gap evaluator found the runQ mechanism unresolved but then allowed the later generic warning to replace it with a false headline: calling apps unverified. A subsequent command-refresh read returned 11 events already present in the original 50-event page. Fallback repeated the Adhan Player name.

## General read-only V2 improvements

- Give source-attested caller evidence during an explicit slow driver-method warning precedence over a generic later hub-load warning. The later WARN interval remains separately described as unattributed, not discarded, and neither establishes hub-wide or callback causation.
- Keep the driver-execution-mechanism-unverified classification with independently typed app IDs when the driver method (for example runQ) is not an observed command. Do not invent a command-runQ API.
- A source-backed overlapping event-history subset is marked redundant when ALL returned projected events (name, time, producer ID and value) were previously observed for the same verified device. Keep all source receipts; prevent repeated rows from displacing new independent evidence in the model view. Partial projections are not classified as redundant.
- Deduplicate calling app names by source-attested app ID across overlapping event reads; never sum duplicate row counts as though they were independent executions.
- When a model proposes a hub_get_device read without deviceId and the host has exactly one independently verified focus target, the rejection returns that ID as guidance only. The host never auto-inserts, executes, or writes a call.
- Regression tests cover the exact 17:04–17:58 slow-method and 19:32–19:55 generic WARN ordering, overlap/scope identity, duplicate issuer prevention, and rejected detail calls.

## Safety and unresolved facts

The source log claims prolonged driver methods and the event history attests app command issuers, but these observations do not establish when driver execution began, whether local clock representations align, or the internal callback mechanism. A high hub-load warning does not, alone, prove measured hub-wide CPU instability. Source-code execution-path reading and atomic claim-to-evidence validation remain outstanding. Experimental Native V2 only; production Main Ask and all Hubitat devices and automations unchanged.
