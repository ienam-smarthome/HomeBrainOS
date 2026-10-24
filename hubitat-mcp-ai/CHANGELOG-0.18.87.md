# HomeBrainOS 0.18.87 — Preserve Groovy-source investigation priority and read-only disconnect messaging

## Live regression (24 October 2026, around 07:33 UK)
The user asked for a **deep READ-ONLY root-cause investigation** of Device Status Report app **3977** and Display device **7182**, including actual Groovy implementation, the observed `LimitExceededException` in `setReportData` (line 64), scheduler callbacks, configuration and scoped logs.

- First browser attempt returned `network-outcome-unknown`, `status_verification=write-outcome-unknown` after a `Failed to fetch` network disconnect. The UI gave instructions for an unknown **write outcome**, although the user explicitly forbade changes. The backend outcome was not received; this event cannot establish that the read actually ran or did not run.
- Second attempt incorrectly matched the generic performance-host optimization route because its text contained both **performance** and **recommend**. It acquired metrics, top-20 stats, 275 scheduler entries, generic logs and high-stat outliers, **but no app configuration or Groovy source text for app 3977**. The final source-completion guard correctly treated it as incomplete, but an incidental app overload causal phrase was incorrectly escalated as an unverified **historical device command** claim.
- The older audit's device-originated exception rows remain evidence of the reported overload. This response supplied no proof of its actual current root cause.

## Fix
- The generic performance shortcut explicitly yields to an installed-app Groovy/source-code request. The normal read-only source agent then advertises the bounded `homebrain_read_groovy_source` workbench (using **installed app ID** rather than assuming it is the code ID) and can inspect current config, actual implementation and logs; it is not preempted by unrelated performance/scheduler inventory collection. Keep generic full-hub optimization behavior unchanged.
- Source-code completion now distinguishes statements like "App 3977 caused excessive hub load" from claims that a named app issued a historical **device command**. Retain strict historical command-event checks for any actual asserted dispatch or command; do not infer code execution or root cause from an error message alone.
- The browser's network-loss fallback treats a **strictly labelled read-only request with an explicit do-not-change directive** as `read-outcome-unknown`, while preserving the conservative `write-outcome-unknown` warning on ambiguous/mutating questions. Neither branch automatically retries or claims the disconnected backend's status is known.
- Regression tests reproduce the exact 3977/7182 question and distinguish general performance requests, command claims and frontend warnings.

## Remaining verification
This patch does **not** prove the Groovy source was obtained in the user's Hubitat environment; that requires a fresh read-only 0.18.87 reply carrying source-tool receipts. It does **not** fix or modify Device Status Report, perform Hubitat mutations, alter paid routing or restore network connectivity. The source-reading path may legitimately report incomplete evidence if the current MCP schema or source-to-instance mapping is unavailable.
