# HomeBrainOS v0.18.72 — Existing-rule read intent and app/device grounding

## Regression observed 23 October 2026

A read-only verification of Rule Machine app 4246 compared with controller app 4019 was reported as `request_class=write`, even though all 11 MCP calls were reads. The prompt asked whether app 4019 **could switch** Livingroom Light 1 **OFF** before a ten-minute timer; the legacy text-only mutation classifier interpreted the hypothetical control action as present authorisation. The result lost its typed `existing_rule_verification` coverage and ultimately refused to report findings about the app's dynamic label as though it were an unverified physical device.

## Changes

- Treat comprehensive **existing-rule verification** questions as read-only when they start with an investigative directive and contain no separately requested state-changing action. Keep independent explicit writes (even in numbered lines or after semicolons) on the guarded write route; do not relax existing write confirmation.
- In the device-identity projection from model tool outputs, exclude records nested under app/rule/automation inventory and configuration keys even when their identifiers are untyped `{id, label}`. Preserve actual device-list and targeted-device-history identities, and continue rejecting genuine unverified device claims.
- Add live-prompt regression tests, read/write contrast fixtures, app-vs-device identity tests and a request-class/evidence-coverage unit test.

## Scope and limits

No Hubitat rule, automation or physical device was changed. This corrects **classification and evidence-grounding**, not the absent typed persisted Rule Machine action-tree extractor. App 4246 configuration and runtime remain partial until verified source evidence is available. Historical device events can provide bounded command provenance without certifying a persisted delay or nighttime operation.
