# Hubitat MCP AI v0.18.343 — vNext source authority and bounded configuration

## Change

The user-run v0.18.342 read-only Bedroom 3 Mesh test verified model-authored publication but revealed unsupported definitive claims about MQTT broker LWT/session state and exact physical telemetry failure, despite no independent broker read, physical observation or verified driver-method source. Model-first fluency improved; grounded accuracy did not pass independent review. 8 model rounds, 7 tools, 37.663 s total. Not a comparable-model or fixed-packet A/B.

This version retains the existing **opt-in** `model_first_investigations_enabled` flag (default off) and adds:
- A typed, privacy-bounded source authority packet generated from already normalized current-turn receipts. Hubitat-saved attributes, bounded mixed state records, disputed metadata ages, driver source verification, broker-origin packet verification and physical proof have separate roles. The model sees this near its last synthesis instruction, instead of guessing which layer `mqttStatus` or watchdog counters prove.
- One additional target-ID-verified, permission-checked `hub_get_device(mode=configuration)` read after state/history/scoped logs when such a read has not already been attempted. No broad inventory, inferred driver code ID or repeated failed source read. This gives the model a chance to inspect driver metadata, not proof of a network cause.
- The same authority status in technical diagnostics under `investigation_coverage.sourceAuthority`.

## Safety

- No hub, device, automation, heater, lighting, broker or Home Assistant changes from repository development.
- The extra source request must pass the live-advertised gateway operation and read-effect checks. An unavailable tool is a missing source, not a reason for an unbounded retry. The existing model-first provisional acceptance rule and legacy source-rendered fallback are unchanged; natural-language factual truth is **not** independently certified.
- No new provider rounds from this change, but an extra MCP configuration read may be needed in the opted-in telemetry case. Actual latency impact is **NOT MEASURED**.
- Tests cover distinct device IDs, missing scoped logs, earlier failed configuration reads, clock conflicts and broker witness attribution.

## Testing

Upgrade v0.18.343; keep `model_first_investigations_enabled: true` **only while testing read-only telemetry** and compare complete answer + Technical JSON against source evidence. Toggle the setting false and restart immediately to restore the established source-rendered publisher if unsupported causes persist. Formal multi-domain quality gate remains **NOT MEASURED**.
