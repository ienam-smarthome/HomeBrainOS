---
name: hubitat-investigator
description: Source-grounded historical and live Hubitat diagnosis; causal timelines, topology, hypothesis testing, and decision-focused follow-up.
version: 1
---
# Hubitat investigation skill

Use for "why?", "what caused?", intermittent, offline, unexplained actions and historical verification questions. This skill guides *investigation*, not a canned conclusion. Prefer an evidence-supported working explanation to a generic unresolved statement, but never turn a likely candidate into a confirmed cause.

## Seven stages
1. Define the subject, exact focal timestamp and transition, user goal, time zone, and evidence required for a cause. For ambiguous matches ask; never silently change target.
2. Discover the real control topology before probing nearby sensors: device -> command-producing app -> app subscriptions/triggers -> physical button/sensor/MQTT/bridge -> reporting device. Identify which rules were active at the focal time if historical evidence exists; current configuration is not historical proof.
3. Build a source-typed timeline: command invocations, reported state boundaries (including immediately preceding OFF), buttons, occupancy, modes, app execution, broker/bridge activity. Preserve full timestamp precision and signed ordering.
4. Inspect anomalies that discriminate causes: command-to-state delay compared with local baselines, intervening OFF or ON reports, previous missing state history, stale resync, duplicate commands, listener-after-action order. A delayed command is a *candidate*, not proof of transport delivery.
5. Maintain competing hypotheses: matching internal command, other internal controller, bridge/direct physical input, state resynchronisation, telemetry defect. Mark each SUPPORTED / PLAUSIBLE / CONTRADICTED / NOT TESTED and cite direct evidence for supporting and opposing claims. A checked-empty bounded event window is not proof of no action.
6. Spend the remaining tool budget on the highest-information checks: inspect the leading producer's app config, its command source (e.g. MQTT topic), and time-filtered logs. Check alternative path configuration only if it could alter the ranking. Distinguish unavailable history from zero events; do not keep asking for already-expired logs.
7. Answer with the *leading recorded candidate*, why it ranks first, serious counterevidence, and the single decisive next test. Separate the command producer, upstream initiator, bridge reporter and downstream listeners. Explain uncertainty precisely.

## Causal confidence
'Recorded X issued on()' needs a direct device event with producedBy. 'X caused the state transition' needs matching delivery/ack, repeated aligned mechanism or equivalent positive provenance and no stronger contradictory evidence. 'Nobody/none of the Hubitat automations did it' requires genuinely exhaustive, time-relevant evidence; rarely supportable from bounded event/log samples. An app's settings cannot prove historical execution.

## Configuration-to-code
Stored app values, effective UI summaries and implemented Groovy branches
are distinct evidence. Before claiming one raw value disables a timer or
recommending a setting change, inspect its handler/default logic via the
installed source reader. Check exact configured activation vs keep-on sensor
IDs and timer cancellation/re-arm conditions. Historical cause additionally
requires time-aligned events; today's active sensor is not proof of yesterday.
If code is unavailable, report unknown semantics rather than guessing.

## Completion discipline
Required source classes should be recorded as checked, checked-empty, unavailable or not checked. For telemetry investigate last *device-originated* packet versus cached health, connection and command acknowledgements; query device-scoped logs where available. For rule bugs inspect configured actions/conditions and their runtime history. If an essential source is not available, describe the consequence for confidence rather than substituting certainty.

## Answer format
Lead with one or two sentences (best candidate + calibrated confidence). Then a short chronological timeline and alternatives with disconfirming evidence. End with actionable, read-only next checks. Avoid boilerplate, duplicated completeness warnings and long unrelated device inventories. Only use facts from current turn or clearly identified time-stamped verified prior records.

## Privacy
Never echo credentials, access tokens, MQTT secrets or raw configuration dumps in the final answer. Read-only investigation is not permission to print secret values.
