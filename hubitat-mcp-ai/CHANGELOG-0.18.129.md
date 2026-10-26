# HomeBrainOS 0.18.129 — V2 test request diagnostics

## Added

- Copy Answer, Copy Investigation Details and Copy Full Report controls with
  secure clipboard use and a fallback for local non-HTTPS Home Assistant ingress.
  Existing V1/Claude textareas accept ordinary Ctrl+V; no secrets are copied.
- Explicit user-dated local incident windows (including UK October DST shift)
  are passed to the planner, enforced for historical event reads, and applied
  to event projection. Current-morning events outside the requested overnight
  period are not displayed as explanations of the earlier incident.
- Increased the V2 planning round's time allowance to 40 seconds (bounded by
  the overall deadline) to avoid premature free-model planning timeouts.

## Fixed

- V2 test UI no longer displays opaque `[object Object]` when FastAPI or
  Home Assistant ingress responds with a structured `detail`. It prints the
  HTTP status and safely summarizes field paths and validation messages.
- Adds client-side preflight of the token length, nonempty question and one
  to four numeric device IDs, preventing avoidable 422 submissions.
- Handles non-JSON/empty success and failure bodies without hiding status.
  Does not echo input payloads, ingress URLs, credentials, or arbitrary HTML.

## Regression evidence

- New FastAPI TestClient tests exercise the actual guarded POST endpoint:
  disabled-mode 404, wrong-token 403, missing explicit opt-in 403, malformed
  question 422, missing live Hubitat ID 422, and a valid 200 response using
  mocked authoritative inventory and mocked read-only V2 evaluation.
- Endpoint success returns non-production answer and honest scorecard data;
  no physical hub or provider was contacted by regression tests.
- Normal production routes, device controls, V1 and read permission boundaries
  remain unchanged.

This patch improves diagnosability; it cannot identify the user's original
server failure without the HTTP response that the previously deployed browser
panel suppressed.
