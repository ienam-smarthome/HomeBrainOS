# HomeBrain v0.17.80 — Recover journal investigations with multiple clock times

## Observed v0.17.79 live regression

The user asked why Livingroom Light 1 turned ON at **19:55 on 14 October 2026** and requested a persistent journal search from **19:50 to 20:00 BST**. The trace retained a verified `command-on` event produced by **SenseCap D1 Settings (4129)** at 19:54:46.691 BST but returned: “it is impossible to identify a command producer.” It also selected an unrelated “most recent” 19:50–20:00 history window on **15 October**, not the requested 14 October incident. The result had `causal_subject_empty_stop=1` but no journal focal read, no scoped producer log read, and no bounded incident state read.

The native/journal source-plan builder rejected all requests containing more than one HH:MM time, including an unambiguous primary event time followed by a separate archival search range. The global causal timeline clock selector had the same restriction. Thus the mandatory early journal source completion was skipped, and the generic empty-history finalization returned an incorrect answer.

## Architectural correction

- Unify the causal event clock selection for the evidence graph and the bounded/journal source planner. A **single clock explicitly attached to an ON/OFF transition** is treated as the focal time, even if the same question gives additional archive-search limits. Otherwise accept a single time in the first question/sentence, then fall back to a unique time in the entire question. Competing explicit transitions remain ambiguous and require clarification.
- Preserve the user-stated calendar day and the verified event timezone offset; no “most recent” clock anchoring can substitute for an explicitly dated focal incident.
- Existing host source completion now runs for this format: check the **persistent journal**, then the native bounded state-history query, and the command producer's app-scoped logs. Never claim archive emptiness without a journal receipt.
- The incomplete-history response now identifies the journal outcome separately: source-stamped state rows, collector-reception-only rows, and recorded connection gaps. Reception-only times cannot prove the precise physical event moment; an empty archive does not prove inactivity.
- Regression tests reproduce the full user request, the recorded command source, an `empty` generic subject history, a collector-received-only archived ON, and enforce journal execution **before** the empty-history stop with no model loops. Additional tests reject multiple competing event times and preserve explicit HH:MM:SS precision.

## Scope and safety

Read-only investigative query routing; no new Hubitat commands, rules, permissions, schedules or storage configuration changes. Native history may have rotated: an existing 14 October journal record may or may not contain the physical switch event. The journal is still opt-in and its data collection was already enabled before this release. Only observed source data may determine the outcome.

## Live acceptance

After upgrading, repeat the previous 14 October event question with the 19:50–20:00 journal range. Verify `skills_focal_journal_read=1`, `skills_focal_state_window=1`, `skills_focal_producer_logs=1`, and the exact 14 October UTC time range. If archived ON is source-timestamped and unique, HomeBrain may reconstruct a state transition, not automatically prove its cause. If only collector-received rows are present, report these as approximate observations and preserve the recorded SenseCap command attribution **as command producer only**.
