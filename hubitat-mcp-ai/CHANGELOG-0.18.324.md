# HomeBrainOS v0.18.324 — Stage 9.0 recent incident report reconstruction

## Live acceptance motivation
On 1 November 2026 the user supplied a read-only Command Shadow result for a hallway light with **11 Hubitat switch-state reports**, five observable ON→OFF pairs and a final ON report. Both `command-on` and `command-off` upstream pages were successfully queried but empty. **No issuing app or physical cause was verified.** This newer incident is a better investigation fixture than the exhausted October mesh-plug source.

## Change
- Add a pure postrun `summarize_reported_transitions` over the **same already-sanitised** Command Shadow result, with no additional Hubitat, Cloud, model, journal or device reads.
- Pair only unambiguous consecutive ON→OFF switch reports ordered by UTC reported event timestamp; do not pair repeated/ambiguous ONs with subsequent OFFs or assume an incomplete page is a whole device history.
- Report time differences between source-reported states (minimum, median and maximum) explicitly as **reported intervals**, not authenticated physical operating cycles, physical runtime or verified clock duration.
- Explain open-ended trailing ON as **no later OFF in returned page**, never proof the lamp is still on. Show partial coverage, row-cap warnings and absence of app-issued command evidence without promoting absence to proof of no command.
- Display the concise, deterministic, evidence-first summary and interval chronology before the raw technical source diagnostics on the phone.
- Preserve false history completeness, clock authentication, physical execution, app causation and publisher approval. No new subscriptions, capture, controls or production AI path.
- All new CI fixtures are synthetic and contain no private household dates/IDs.

## Limitations
The existing Command Shadow reads remain three fixed bounded Hubitat event-history requests for one numeric ID and UTC day, behind their separate explicit consent. The new summary is *not Gemma-generated*. It does not prove whether a reported OFF was caused by an inactivity timer, manual control, motion, button or any automation. To investigate the cause, a validated controlling-app ID and independently preserved, scoped app-decision/command evidence are required; never invent an app ID from a state pattern.

## Phone acceptance
Upgrade to `0.18.324`, open **Live Shadow → Command Shadow**, enter the selected device ID `7829`, UTC incident date `2026-11-01`, tick the **read-only Hubitat device-events** consent and choose **Compare command and switch events**. Inspect **Recent switching investigation · reported events only**, the paired report intervals and causal limits. If older history is no longer available, select a *newly occurring* naturally recorded incident rather than making live device changes.

Rollback: revert this PR to v0.18.323.