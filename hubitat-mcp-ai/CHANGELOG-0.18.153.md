# HomeBrainOS v0.18.153 — Fast, source-backed read-only answers when AI planning stalls

The live .152 V2 test asked about Livingroom Light 2 (#7828).
The server independently verified the device (20.409-second complete
inventory), recovered the read-time reported switch=on and networkStatus=online
with eleven timestamped switch reports, but waited 60.003 seconds for the
optional model to propose deeper reads, then presented a generic partial
investigation. The report omitted the three most recent switch transitions
(21:59:01 ON, 21:59:08 OFF and 21:59:17 ON on 26 October), and added an
irrelevant MQTT-client connectivity disclaimer for a light without MQTT
attributes.

## Changes
- Opt-in V2's optional model read-planning round is bounded to 15 seconds
  rather than 60 seconds. An unavailable or slow model never suppresses
  already-authenticated read-only device facts.
- Host-grounded reporting begins with the actual current reported switch,
  networkStatus and other relevant source values, and the most recent switch
  event's value, source and timestamp. An event source is not misidentified
  as the initiating controller.
- The compact timeline includes first and last important switch transitions,
  not just the oldest eight, while canonical evidence retains all events.
- Grounded synthesis now includes networkStatus. MQTT and power/energy
  warnings are emitted only when the actual projected snapshot has those
  attributes. No fabricated physical outcome, transport layer, or control
  command.
- Synthetic tests replay #7828's eleven events, reporting parent #7790,
  last-three timeline retention, status and credential sanitisation.

## Scope and limits
This remains a read-only V2 test route; it cannot and must not actually
turn lights on/off. Existing production V1 command paths, explicit write
confirmation, apps, devices and rules are untouched. The 20-second full
inventory request and incomplete controller attribution remain open
architectural performance/evidence issues. The 15-second model ceiling
intentionally degrades to a clear fact-based report if the configured
AI provider cannot respond within the budget. It does not prove a causal
root cause.
