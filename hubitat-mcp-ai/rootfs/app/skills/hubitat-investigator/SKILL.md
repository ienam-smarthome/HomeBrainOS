---
name: hubitat-investigator
description: Source-grounded historical and live Hubitat diagnosis; causal timelines, topology, hypothesis testing, and decision-focused follow-up.
version: 1
---
# Hubitat investigation skill

Use for "why?", "what caused?", intermittent, offline, unexplained actions and historical verification questions. This skill guides *investigation*, not a canned conclusion. Prefer an evidence-supported working explanation to a generic unresolved statement, but never turn a likely candidate into a confirmed cause.

## Seven stages
1. Identify the subject, time/window, timezone and causal question; never change targets.
2. Trace device → command app → configured subscriptions and physical sensor/bridge.
3. Time-order commands, physical events, intervening OFF, input edges and delays.
4. Test missed telemetry, resync, conflicting commands and event/listener order.
5. Compare supported, plausible, contradicted and untested hypotheses.
6. Read the strongest missing app config, source method, sensor history or app log.
7. State the leading supported cause, alternatives and decisive next check.

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

For occupancy lighting, use the controller's actual configured activation/keep-on IDs; check each input's history. Cloned/virtual sensor activity is not independent physical occupancy evidence. Compare event listeners with the controlling app, and verify OFF commands against subsequent switch states before asserting timer causality or ghost motion.

## Completion discipline
Required source classes should be recorded as checked, checked-empty, unavailable or not checked. For telemetry investigate last *device-originated* packet versus cached health, connection and command acknowledgements; query device-scoped logs where available. For rule bugs inspect configured actions/conditions and their runtime history. If an essential source is not available, describe the consequence for confidence rather than substituting certainty.

## Answer format
Lead with one or two sentences (best candidate + calibrated confidence). Then a short chronological timeline and alternatives with disconfirming evidence. End with actionable, read-only next checks. Avoid boilerplate, duplicated completeness warnings and long unrelated device inventories. Only use facts from current turn or clearly identified time-stamped verified prior records.

## Privacy
Never echo credentials, access tokens, MQTT secrets or raw configuration dumps in the final answer. Read-only investigation is not permission to print secret values.
