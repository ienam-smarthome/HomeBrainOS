# HomeBrainOS 0.18.165 — V2 to Ask control handoff

## Live usability issue

On 27 October 2026, entering "Turn on Livingroom Light 2." in the
Investigation V2 test page correctly resulted in HTTP 409
(v2_control_not_supported) before any device read/write. The user then
saw a separate 41.382-second semantic device-inventory report
(36.909 seconds inventory; 4.471 seconds planning), which is read-only
and unrelated to command execution. The control request was never sent.

## Improvement

- Keep Investigation V2 strictly read-only, without capability or API changes.
- Place a clearly labelled **Open main Ask / device control** link beside
  Run V2 read-only test, where the user actually submits questions.
- When the API returns the expected control-intent HTTP 409, reveal a
  prominent explanation, **Copy control request** button and an
  **Open main Ask** navigation link. Nothing is auto-submitted.
- Navigation stays same add-on-origin and carries no V2 operator token,
  saved browser access token or other credentials. Only explicit
  clipboard action copies the user's control question.
- Preserve existing server-side permission/confirmation checks for all
  device writes; neither the page nor the V2 token grants write access.

## Verified regression checks

The test page exposes navigation controls near the action button and
after a 409, the refusal clears stale prior test output, and no
cross-interface fetch, implicit submit, credential storage or raw HTML
injection is introduced. The existing HTTP safety suite still asserts
that direct ON/OFF commands are rejected before inventory or AI use.

## How to test live control

1. Update and restart the add-on to v0.18.165.
2. On V2, try "Turn on Livingroom Light 2."; it must reject quickly,
   present the main Ask link, and send no Hubitat action.
3. Click **Copy control request** then **Open main Ask**.
4. Paste the request into the main HomeBrain Ask field and submit.
5. For a safe, deliberately chosen light, check the reported command
   receipt from v0.18.164, then request a fresh Hubitat state read.
6. Do not interpret a waitFor ack as independent physical confirmation.
   No automatic retry on missing acknowledgement.

No live Hubitat device mutations were performed in CI.