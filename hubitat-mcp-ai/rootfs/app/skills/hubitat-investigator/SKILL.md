---
name: hubitat-investigator
description: Source-grounded historical and live Hubitat diagnosis; causal timelines, topology, hypothesis testing, and decision-focused follow-up.
version: 1
---
# Hubitat investigation skill

Use for "why?", "what caused?", intermittent, offline, unexplained actions and historical verification questions. This skill guides *investigation*, not a canned conclusion. Prefer an evidence-supported working explanation to a generic unresolved statement, but never turn a likely candidate into a confirmed cause.

## Seven stages
1. Define the exact subject, focal time/window, timezone and requested cause. Never change targets silently.
2. Trace real topology: target device -> command-producing app -> configured triggers/subscriptions -> physical sensors/buttons -> bridge reporter. Current settings are not historical execution proof.
3. Build a timed event table: command invocation, physical state edges, intervening OFF, manual button, motion, app execution and delays.
4. Investigate discriminating anomalies: missed telemetry, repeated commands, source timestamps, state resync and listener-after-action ordering.
5. Compare hypotheses (app command, alternate controller, external bridge, stale reporting). Mark SUPPORTED, PLAUSIBLE, CONTRADICTED or NOT TESTED; a checked-empty window is not proof of no execution.
6. Read the strongest missing source: command producer app config, relevant source methods, and bounded producer logs. Avoid obsolete log windows and unrelated inventories.
7. State the strongest recorded candidate, serious contradictory evidence, what remains unknown and one decisive next test. Separate initiator, command producer, bridge reporter and downstream listener.

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

For occupancy-controlled lighting, first obtain the **effective configured** activation and keep-on device IDs from the controlling app (including UI/runtime semantics). Check recorded activity for **each configured input**, not just nearby or easily retrieved room sensors. A virtual, cloned or mirrored sensor is not independent physical occupancy evidence and must not be treated as a controller input merely because its activity aligns in time. Compare the sensor event's triggered-app listeners with the claimed controller: a listener/bridge event is different from an app-issued OFF command, and an absent controller listener does not prove timer participation. Verify the actual OFF command and subsequent state transition; two aligned OFF sequences cannot establish that every historical timer decision worked. An active sensor is not proof of a physically occupied room, and 'ghost motion' requires independent vacancy evidence.

## Completion discipline
Required source classes should be recorded as checked, checked-empty, unavailable or not checked. For telemetry investigate last *device-originated* packet versus cached health, connection and command acknowledgements; query device-scoped logs where available. For rule bugs inspect configured actions/conditions and their runtime history. If an essential source is not available, describe the consequence for confidence rather than substituting certainty.

## Answer format
Lead with one or two sentences (best candidate + calibrated confidence). Then a short chronological timeline and alternatives with disconfirming evidence. End with actionable, read-only next checks. Avoid boilerplate, duplicated completeness warnings and long unrelated device inventories. Only use facts from current turn or clearly identified time-stamped verified prior records.

## Privacy
Never echo credentials, access tokens, MQTT secrets or raw configuration dumps in the final answer. Read-only investigation is not permission to print secret values.
