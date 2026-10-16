# HomeBrain 0.17.83 — explain archived collector-received transitions

## Why
The 0.17.82 Historical Journal browser displayed archived OFF/ON/OFF/ON reports for Livingroom Light 1 on 14 October 2026, including a SenseCap D1 Settings ON command, but the causal answer reduced four reception-only switch rows to a number and said the historical ON was not independently verified. This omitted decisive investigative context.

## Changes
- Retain a source-scoped, chronologically sorted, short (maximum 12) **reception-only switch transition sequence** in the existing host-owned `focal_archived_state_history` receipt, alongside the separate source-timestamped events.
- When exact historic source-state proof is unavailable, explicitly render OFF/ON report values and collector-reception times in the deterministic final answer. Convert into the question's existing, evidence-derived local offset for readability.
- Highlight an intervening collector-received ON/OFF/ON as a competing-explanation trigger and name specific follow-up evidence: upstream SenseCap/MQTT origin, command handling, and Hue Bridge events.
- Disclose when the journal query was capped or the short rendered receipt omits older observations.
- Do **not** promote collector timestamps into verified source/physical state time or claim that a preceding ON command caused the second activation. No new hub polling or writes.
- Add regression tests reproducing the live 14 October timeline, a zero-data case and result-limit handling.

## Validation
All code must pass GitHub Actions before merge and add-on deployment. Post-install, rerun the exact read-only 14 October question; final text should expose the collector OFF/ON/OFF/ON sequence, retain source provenance (app 4129), and clearly state that physical event time/upstream causation remain unverified. No runtime journal schema or capture-setting changes.
