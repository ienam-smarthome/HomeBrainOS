# Hubitat MCP AI v0.18.344 — verified driver source and conflict-aware publication

## Observed regression

The real read-only v0.18.343 Bedroom 3 Mesh answer was original Gemma prose, not host-rendered, but still asserted an unobserved live MQTT broker/LWT condition and total physical telemetry silence. Technical evidence showed 502.6 versus 45.1 hours for separate cached age metadata, no independent broker observation, no driver implementation read and no physical-cause proof. This remains a failed factual-grounding review. The answer happened to suggest driver code ID 3686, but that prose is *not* source identity attestation.

## Changes (opt-in only)

- Device-configuration results retain a privacy-minimal, **explicitly device-linked** driver code ID when unambiguous. Reject wrong device, guessed instance ID, multiple candidate code IDs, app source identifiers, and failed reads.
- After a current-turn verified driver ID is present, the host can request **one** read-only `hub_get_source(type=driver)` chunk with a bounded 8,000-character page. The gateway must actually advertise the operation and a nonmutating effect. No unbounded paging, code guessing, tool-permission expansion or extra provider round.
- Technical source authority records when a code chunk was linked and retrieved; reading code is **not proof of verified method behavior**. No raw source, secrets or driver settings are retained in API evidence.
- On unresolved contradictory telemetry metadata with no independent upstream and method verification, the existing source-rendered explanation is the fallback. This is a source-conflict general gate, not a room/phrase-specific publication patch; natural model text remains provisional elsewhere.

## Tests and rollback

Synthetic tests cover target linkage, non-target and ambiguous IDs, duplicate source reads, source chunk provenance and conflicting clocks. Tests do not prove model accuracy. The default `model_first_investigations_enabled=false` remains unchanged, and turning it off and restarting restores the established source-typed renderer. No live Hubitat or HA devices, rules or configurations were changed. Official model-quality score remains **NOT MEASURED** pending human-reviewed read-only acceptance.
