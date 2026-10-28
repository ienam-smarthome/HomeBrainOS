# HomeBrainOS v0.18.197 — Incident-time evidence and model causal-claim gate

## Live regression (28 October 2026, v0.18.196)

The V2 test completed in 24.245 seconds with seven successful READs and its first fully model-authored explanatory narrative. It correctly resolved Google Nest Hub device 7934, three generic load warnings at 19:55:19.194–19:55:19.399, and command issuers Adhan Player (app 1679) and 00 Google Calendar Notifier (app 4080). The app code request returned status=success and appId=1679 but **no code** (correctly reported).

The explanation, however, called Adhan Player the **most material offender**, asserted its ~1 Hz refresh polling loop was a *likely driver of* the 19:55 warnings, and speculated that network polling is expensive—none of which was established by the sources:
- Eleven app-issued refresh events clustered around 18:14:51–18:15:02, about 100 minutes *before* the 19:55 warning; not contemporaneous app commands.
- Eleven playTrack commands were counted across multiple days, not the ~10-second refresh burst.
- Device-generated media status/mediaSource events cluster at 19:55:19.193–19:55:19.398, overlapping printed WARN timestamps; no independent execution path, clock equivalence or CPU cost is established.
- Gateway source-content unavailable, and hub-wide load was not measured at warning time.
- `hub_list_app_pages(appId=1679)` succeeded but projected as uninterpretable despite returning a navigation envelope.

## General-purpose fixes

1. **Incident-temporal evidence packet.** For any uniquely verified target with a generic WARN and device-scoped event history, the host derives incident timestamps, app issuer identities, command counts within the warning and five-minute windows, nearest earlier/later command by unzoned source-clock times, actually observed command bursts, and source-clock-nearby device state transitions. It explicitly discloses event caps, clock uncertainty and that a burst is a hypothesis lead, not an incident cause. The packet is available to the model during investigation; it neither selects tools nor grants permissions.
2. **Independent final-claim gate.** A model-authored answer may cautiously report observed commands or unknown causality. When it *ranks or asserts* a culprit for an incident whose sources remain unattributed and unprofiled, the host rejects the unsubstantiated causal ranking and substitutes a concise, independently derived incident explanation. It records `unsupported_causal_ranking_withheld` in diagnostics and validation issues, requiring human review. This is a final-answer evidence check, not keyword-based question routing and not a claim that full atomic verification exists.
3. **Burst versus total separation.** Dense same-app/same-command events are analysed as bounded contiguous bursts with actual start/end; per-command totals across days do not become burst counts. The source-clock gap between such a burst and the target generic warning is explicitly retained.
4. **App-page navigation projection.** `hub_list_app_pages` now retains safe page names, page count, primary page and source-reported app identity without reflecting settings values, form contents, code, HTML, endpoint URLs or notes. It is labelled navigation metadata, not configuration or execution evidence.
5. **Safety invariants.** No new Hubitat reads are launched automatically; all calls remain model selected and checked by the authenticated read manifest and typed IDs. No writes, Main Ask changes or device-specific routing.

## Tests and remaining limitations

Live-shaped tests replay the command-burst versus ~100-minute warning separation, all relevant device-owned status transitions, app-page privacy, the withheld model-authored "most material offender" answer, and a grounded fact-only answer that remains intact.

The ranking gate uses conservative final-text causal-attribution patterns and **is not complete claim-by-claim natural-language verification**. Timestamp comparisons use printed wall-clock values without independent timezone confirmation. Capped returned events cannot prove no missing commands. Code inspection, driver call-graph analysis and runtime CPU attribution remain unverified. Future work should extend claim verification to an explicit structured claim ledger with evidence citations, rather than accumulating task-specific rules.
