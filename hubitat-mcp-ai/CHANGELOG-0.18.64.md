# HomeBrainOS 0.18.64 — Unknown rule-write outcome after browser/network disconnect

## Incident
User requested creation of an active native Rule Machine TEST automation (Livingroom Light 1 device 7805, FP400 device 7978, 23:00–06:00, ten minutes continuously inactive). The v0.18.63 web UI returned only `{"success":false,"route":"error","message":"Request failed: NetworkError when attempting to fetch resource."}`. No operation/confirmation evidence accompanied this result. This is a **browser to HomeBrain transport error**, NOT evidence of a Hubitat rule write failure or success. Exact cause (HA ingress expiry, add-on restart, browser connectivity, backend fault, etc.) is unknown without add-on/browser logs.

## Code findings
- Web UI calls `fetch(api/ask)` once and, on generic exceptions, used `route:error` plus a raw exception. It gave no warning against retrying write commands.
- Backend `RequestCoordinator` detects disconnection and cancels the in-flight task. Cancellation cannot reverse an earlier Hubitat write/confirmation that might have executed before disconnect.
- The live user result has no native Hubitat verification, so do **not** automatically repeat the active-rule creation request.

## Fix
- Mark fetch rejection specifically as `network-outcome-unknown` and `status_verification=write-outcome-unknown`, with a clear rule/device write warning to inspect Hubitat's exact named rule before any retry.
- Display a request ID for correlation with backend logs; do not expose prompt bodies, API credentials, session secrets or query data.
- Preserve explicit browser user-cancellation behavior (AbortError) and all existing backend confirmation controls.
- Log safe request ID on backend detected disconnection, with clear indication that direct Hubitat verification is required. No automatic replay, task extension, new rule/device action or change to cancellation semantics.
- Regression tests verify UI fail-closed wording, absence of automatic retry, and request cancellation logging.

## Remaining diagnosis
If network failures persist, inspect Home Assistant add-on logs around the request time, browser developer Network tab (especially `/api/ask` and ingress responses), Hubitat's Rule Machine installed rule list, and backend version/restart history. This patch **does not** establish why the network dropped or prove the new test rule exists. Follow-up feature: durable, opt-in request outcome ledger and idempotent native write confirmation, designed to avoid duplicate rules when clients disconnect.

All repository CI must pass before merge.
