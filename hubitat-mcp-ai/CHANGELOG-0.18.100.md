# HomeBrainOS 0.18.100 — Concise TV usage breakdown including ongoing periods

## Observed production regression (24 October 2026)

HomeBrainOS 0.18.99, asked "how long has the TV been on today?", returned "1 hour 46 minutes" despite retaining a typed TV switch history with a 13-minute post-midnight inferred carry-over and a 16:37–16:49 ongoing period of about 12 minutes. It then appended an irrelevant "Investigation completeness: partial; unchecked command_history" notice and displayed the outcome as Unresolved. A separate Claude response included both periods and showed a concise ON/OFF breakdown.

## Fix

- For a simple elapsed-time "today" question with a single verified target switch-history receipt, compute the rounded daily estimate from (1) completed observed ON/OFF intervals, (2) an optional predecessor-ON/first-OFF midnight carry-over, and (3) a still-open observed ON interval measured to the receipt's actual as-of timestamp.
- Require a target-bound, time-consistent observed opening transition and confirm the model-independent open-duration seconds agree with the receipt before including an ongoing interval. If the open edge is inconsistent or missing, do not silently display the completed total as a complete daily figure.
- Render a compact, auditable Markdown ON/OFF/duration table from typed event boundaries, including 00:00 to first OFF as explicitly inferred and an ongoing "Still on" row. The table is withheld if observed interval rows are missing, truncated or inconsistent.
- Present the current state as the **latest recorded** ON/OFF event, never as independently verified physical packet delivery. Qualify inferred and open intervals as an estimate of smart-plug switch-on time, not actual TV screen time.
- Remove spurious historical-command provenance requirements from factual duration answers. Reclassify a previously "Unresolved" factual answer as success only when the typed duration projection succeeded and there are no genuine refusal, evidence-incomplete, failure or missing-target counters. Preserve such genuine failures.
- Preserve read-only behaviour, model/tool cost selection and evidence integrity constraints. This is generic for any single switch-history device, not a per-TV keyword-specific route.

## Live regression

At 16:49:08 Europe/London, the observed completed spans were 6349 seconds, the valid open span 709 seconds, and the inferred pre-midnight carry-over 775 seconds: 7833 seconds, or about **2 hours 11 minutes**, over five displayed periods. As-of 16:50 the ongoing period would grow by another minute, matching the later Claude estimate of about 2h12m. A synthetic replay and earlier closed-interval tests validate both paths; live deployment still requires user upgrade and retest.

No Hubitat automations, devices, rules or settings were changed.
