# Hubitat MCP AI v0.18.226 — Joined source-event chronology

## Why

The 29 October live v0.18.225 Bedroom 3 Mesh test correctly found an
app-3950 OFF instruction at 2026-10-12T01:30:01.743+0100 and reported a
0.743-second gap to the *rounded* device lastSeen attribute. But it omitted
more discriminating facts already contained in the same approved device-event
read:

- at 01:30:01.908 BST, a device-produced `lastSeen` event
- at 01:30:01.914 BST, a device-produced `switch=off` event
- at 01:33:46.925 BST, a device-produced `healthStatus=offline` event

These were **0.165s**, **0.171s** and **225.182s** after the app command,
respectively. A Hubitat state event does not prove physical power switching,
a driver health status is not a genuine device heartbeat, and this observed
sequence still does not prove the app caused the outage.

## Implementation

- Extend the generic, independently source-ID-checked V2 temporal lead:
  retain existing source-attested command issuer samples and additionally
  examine the bounded, already-projected event history.
- Admit event timestamps only with explicit timezones and structured producer
  identities, matching the independently verified target device ID or
  app-issued command ID. Source-projected free-text event descriptions and
  private command args are never interpreted as event facts.
- Find the nearest separately recorded contact event, matching switch-state
  event (for `on`/`off` commands) and reported offline-health event in
  short, time-bounded windows. Preserve event read IDs and source-reported
  limitations. Do not invent unreturned state transitions or verify
  physical power from driver reporting.
- Compare all bounded projected command events, not only the five example
  samples kept per app, while deduplicating overlapping event pages.
- Recognise when the same-session, identity-matched `hub_get_app_config`
  metadata was already retrieved. Avoid advising the user to repeat an
  inspection already attempted when rule actions, settings values and
  historical execution are still unavailable.
- Return the verified chronological sequence to the model's ordinary
  model-chosen, READ-only source transcript and the independently checked
  concise answer. No new tool invocation or question-name-specific routing.
- Preserve production controls, MCP tool-effect guards, permissions and
  read-only experimental V2 boundary.

## Regression tests

`pytest -q tests/test_investigation_v2_event_sequence_0_18_226.py`

The tests cover exact source timestamps from the failed incident, unrelated
device producers, misleading app-originated state events, unverified app
configuration IDs, absent switch confirmation, far-away timestamps,
repeated source pages, and an event page with more than five commands.

All full CI suites and container smoke validation must pass before merge.

## Live test

"Investigate why Bedroom 3 Mesh stopped communicating around 12 October 2026.
Correlate app-issued commands with individually timestamped lastSeen, switch
and health-status event records. Inspect actual app settings or execution
history where read-only tools permit it, and distinguish Hubitat-reported
states from proven physical power or network communication. Read only."

**Acceptance:** The answer should identify the 01:30:01.743 OFF command,
01:30:01.908 lastSeen event, 01:30:01.914 OFF state event and
01:33:46.925 offline-health event when those same source rows are still
available. It must clearly state that the rule remains the leading
time-correlated explanation, not an independently verified physical cause.

## Open issues

This release does not prove the actual rule's scheduling/action configuration,
physical device power-off, whether later ON commands reached the plug, or an
alternative Wi-Fi/MQTT/network failure. More hypothesis-directed, read-only
automation log and causation checks remain necessary.
