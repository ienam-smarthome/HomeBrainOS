# HomeBrainOS v0.18.194 — Scoped history integrity and bounded invalid READ recovery

## Why this release

The 28 October 2026 23:11 v0.18.193 Native V2 experiment took 23.789 seconds with four successful MCP reads, but produced no device-call attribution. The model uniquely resolved Google Nest Hub device 7934 and retrieved three source-backed excessive-load WARN rows between 19:55:19.194 and 19:55:19.399. It next requested `hub_get_logs(mode=devices, deviceId=7934)`, which took 7.773 seconds but returned one uninterpretable row, then called `hub_list_device_events(limit=100)` **without deviceId**. The gateway correctly returned 26 hub/location mode and backup events, not the Nest Hub history. Three subsequent proposals for `hub_get_device` omitted the required deviceId; all were rejected. The agent spent another 8.003 seconds in a failed model-only synthesis and fell back to a source summary.

The earlier v0.18.192 trace separately established that app 1679 (Adhan Player) and app 4080 (Google Calendar Notifier) had issued device commands; the present run's missing caller result reflects incorrect tool selection, not a newly established lack of device callers.

## Fixes

- Add a source-backed READ-scope validator: when a single device identity is independently verified and logs attest WARN/ERROR observations for that same device, **hub_list_device_events without deviceId/appId or an explicitly declared hub/location mode is rejected locally**. Its unscoped hub events cannot silently pass as causal device history.
- Return an explicit recovery hint with the previously verified deviceId for both unscoped target history and missing-required-deviceId failures. This is *advice only*: the model must resubmit a valid read. The host never inserts a target ID or executes a rejected read.
- Count model-proposed read-contract errors per operation and stop after repeated failed arguments when a round returns no accepted reads. Avoid another unproductive third malformed `hub_get_device` attempt.
- If the model repeatedly violates a required read contract while verified target WARN evidence exists, use the source-backed safe fallback without waiting a further eight seconds for a separate final model-only synthesis.
- Retain explicit hub/location history requests and general whole-hub investigations. No keyword routing, no automatic Hubitat reads/writes, no permissions expanded.
- Add regression tests replaying malformed target-history reads, model-guided repair, repeated missing IDs and early safe fallback, plus a contrasting valid hub/location history request.

## Open constraints

Source history can remain incomplete, warning cause and impact are not independently verified, and a source-backed warning is not necessarily proof of a blocked driver callback. A slow mode=devices log-tab call may still be permitted if the model expressly chooses that investigative source, but its uninterpretable response must not be claimed as evidence of normal performance. Full driver-source reasoning and atomic claim-to-evidence validation are still outstanding. Experimental Native V2 only; production Main Ask and live Hubitat automations unchanged.
