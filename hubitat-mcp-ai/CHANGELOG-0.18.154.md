# HomeBrainOS v0.18.154 — V2 Intent Boundary and Controlled Testing

The user asked HomeBrain to turn Livingroom Light 2 on. Investigation V2
instead treated the command as an investigation, verified device #7828,
performed two read-only historical lookups, spent 60 seconds waiting for
an AI planner, and reported that the light was already ON. **It issued no
`on()` command** because the test interface is read-only. This was an intent
and UI failure, not a failed Hubitat device actuation.

- **Negative-only mutation boundary:** Reuse HomeBrain's existing
  production explicit mutation intent classifier, with an additional
  conservative lead-in denial for compound direct control requests that
  are deliberately disallowed from the production shortcut parser.
  No write routing or authorization is granted by the V2 classifier.
- **Early safe rejection:** After V2 operator authentication but BEFORE
  inventory, AI classification, live device reads or any MCP interaction,
  the V2 API returns HTTP 409 with a stable `v2_control_not_supported`
  code and an explanation to use the normal HomeBrain Ask/Chat UI.
- **No misleading result:** The V2 browser presents the incompatibility
  as a clear guidance message, not a report claiming the light was turned
  on. The UI cannot forward a request to the production write endpoint.
- **Regression coverage:** Direct, polite and compound write requests,
  historical questions mentioning ON/OFF, explicit read-only instructions,
  authentication-before-intent, no inventory/AI/MCP calls for rejected
  writes, and safe browser handling.
- **Testing readiness:** The new
  [Investigation V2 test matrix](docs/INVESTIGATION-V2-TEST-READINESS.md)
  defines broader read-only tests and production exit criteria.

Only the opt-in V2 test route changes. Production V1, live Hubitat device
commands, write confirmations, installed automations and safety permissions
are unchanged. V2 still is **not production-ready as a replacement for
HomeBrain's general Ask/Chat and write workflows**.
