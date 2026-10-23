# v0.18.75 — Existing-rule editor row recognition and safe page diagnostics

## Observed live regression
The v0.18.74 audit of app 4246 read both native Rule Machine editor pages successfully, with **2 trigger paragraphs** and **8 action paragraphs**, but all `recognizedActionRows` were empty. The parser was anchored to action verbs at the start of a paragraph and could miss numbered, bulleted or step-prefixed rendered action rows. The actual raw paragraph text was not retained, so no exact format can be certified from the live receipt.

## Changes
- Recognize a strictly bounded `Action N:`, `Step N:`, numbered and bulleted presentation prefix **only at the start of a paragraph** before testing the allowlisted syntax tokens (Cancel Delayed Actions, IF/ELSE/END-IF, Delay, On and Off).
- When no action syntax is recognized, retain **deidentified count-only diagnostics**: paragraph count, numeric/bullet formatting, HTML presence, too-long/multiline/non-string counts, and counts of six known syntax mentions. Never reveal editor prose, names, conditions, private settings, credentials or URLs through receipts or rendered diagnostics.
- Render count-only observations in the partial report to make the next test actionable if the native editor uses another structure.
- Preserve ID/page matching, no model-authorized writes, and `stored_logic=checked-unverified` / `evidenceComplete=false` without a separate authoritative compiled action-tree export.

## Boundaries
Observed page text is **not** a verified native actionList, and help-text mentions cannot be promoted to actions. This change improves parsing of plausible presentation formats and adds safe diagnostics, but does not establish how app 4246 actually renders its eight paragraphs until it is retested live.

No Hubitat automations, devices, timers or schedules are changed.
