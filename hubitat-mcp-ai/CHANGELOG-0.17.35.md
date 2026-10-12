# HomeBrain 0.17.35 — Historical motion-lockout sequence investigations

## Live regression: app 4019, Livingroom Light 1

The first generalisation test asked whether a **manual OFF followed by motion** activated the Livingroom Light 1 three-minute lockout. Version 0.17.34 returned a generic "Rule Machine investigation" containing current app configuration, four current sensor states and three bridge-health reads, despite **zero** historical light/physical button/motion evidence reads and no Historical Journal checks. It reported success after 8 tools / 2.8 seconds but did not answer whether the historical lockout engaged.

## Architecture

- Introduce a narrowly scoped **temporal-lockout investigation** policy for questions explicitly concerning manual/physical OFF, motion and lockout/inhibition. Do not replace these requests with a present-day configuration or health inventory.
- Deterministically resolve the user-named light using exact device identity and obtain its bounded switch-event/interval history before the model authors a verdict. If identity or a bounded OFF cannot be found, return a partial evidence status rather than fabricating the event.
- Select the latest *observed* closed OFF as a candidate, explicitly **not** a verified manual OFF. To prove manual initiation requires independent controller/command evidence.
- Use the named app's current configuration (where available) only to identify relevant configured motion sources, including named cross-room sensors. Read a narrow app-log window around the candidate OFF for execution evidence.
- Read relevant light/button/motion histories from the already-persisted Historical Journal over the candidate OFF and subsequent three-minute interval. Compare button proximity and motion changes with any ON events, preserving source-versus-collector timestamp uncertainty, incomplete history, and gap caveats.
- Feed a typed, bounded source summary to the final-answer synthesizer, together with explicit obligations to distinguish **manual OFF association, motion, subsequent light ON and historical lockout execution**. An absence of ON does not prove that an inhibition timer ran; current "lockout inactive" is not evidence of historical state.
- Use registered tool accounting for direct MCP reads when the gateway is available, without putting raw app-log messages in technical evidence. No additional background collection or Hubitat polling.

## Tests and safety

Regression coverage includes actual app 4019 wording, false routing positives, exact identity matching, relevant cross-room motion and separated button devices, latest-off selection, bounded journal observations, absence of execution-proof inflation, and an unmatched-subject fallback.

**Read-only.** No device commands, rule/app edits, new automations or modified journal settings. Seven-day / 200,000-row retention remains unchanged.

## Live verification

After updating to 0.17.35, repeat:

> Investigate the latest manual OFF followed by motion for Livingroom Light 1. Determine whether app 4019's three-minute motion lockout engaged, separating physical button events, motion events, and automation decisions. Read-only.

A passing answer must identify the chosen OFF timestamp, distinguish a true/only candidate manual OFF, compare actual motion and subsequent switch events in the correct three-minute window, and state whether any app-log entry independently establishes the lockout. If none does, answer **historical lockout activation unverified**, not success. Check technical evidence for `homebrain_motion_lockout_investigation` and `Historical Journal` device scopes.
