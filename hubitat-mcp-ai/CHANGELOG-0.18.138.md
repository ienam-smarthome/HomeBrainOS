# HomeBrainOS v0.18.138 — everyday state-duration questions in V2

- Resolve **today** (local midnight to request instant) and **yesterday** (previous local midnight to today's midnight) using the authoritative Hubitat timezone, retaining DST day length and explicit UTC fallback when unavailable. Fixed-date forensic semantics remain unchanged.
- Recognise unique short device labels used as complete, contextual noun phrases (e.g. “the TV”), while preserving strict ambiguous-name and full-id verification.
- If a model proposes a `hub_list_device_events` or `hub_get_device` read without deviceId, the host may supply it from a *single* independently verified target, then apply the full original MCP manifest/schema/effect gate. No tool-supplied conflicting ID is replaced, and no multi-device target is guessed.
- State-duration questions use **generic host-side switch-interval arithmetic**, not speculative root-cause planning. Each ON/OFF pair contributes a timestamped session, and a final ON is projected to the request time *conditionally*. Missing states never become a made-up zero duration; a source with unproven completeness is explicitly caveated, as is plug ON-time versus actual TV viewing.
- No change to production V1, Hubitat write permissions or confirmation workflows. This remains explicitly enabled read-only test mode.
