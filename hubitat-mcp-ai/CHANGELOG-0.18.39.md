# 0.18.39 — Evidence-directed historical app-log reads

## Motivation
In the 0.18.37 Bedroom 3 Mesh investigation, Hubitat device history identified an app-produced OFF command. The model nevertheless called device-event history using an appId, which did not establish the corresponding app execution logs. This release adds a narrow read-only obligation to retrieve the more decisive source when available.

## Changes
- Find a uniquely identified command producer using typed, successful event evidence and verify that the requested target device is independently matched.
- Convert the explicitly supplied incident time (BST/GMT) into UTC and select a ten-minute interval either side.
- Select the registered read-only diagnostic gateway and query that particular app's logs before final synthesis. Do not infer an app ID from titles or model prose.
- Do not repeat an app-log query that already covered the incident, whether it succeeded or failed; do not treat wrong-window or device-event reads as matching app-log evidence.
- Keep physical device actuation, automation trigger and complete historical coverage unresolved unless separately established.
- Record counts for attempted, unavailable or failed provenance app-log reads.

No Hubitat changes or provider-route changes. Free Gemma remains the default. Existing collapsible chat interface is retained.

## Tests
A regression suite reconstructs the historical device command, checks app identity and UK-to-UTC conversion, suppresses duplicate queries, rejects mismatched subjects and competing producers, and verifies one final-stage read using a permitted gateway. All three CI workflows must pass before release. Live behaviour and actual inference speed require a subsequent add-on test.
