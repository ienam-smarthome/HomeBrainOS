# v0.18.25 — Historical Rule Machine execution must not use the configuration-only shortcut

## Live regression (0.18.24)

The user asked whether Rule Machine/power-saving app 3950 had **actually issued an OFF command** to Bedroom 3 Mesh, device 7103, at about 01:30 BST on 12 October 2026. HomeBrain returned in **368 ms**, with **zero model rounds** and a single `hub_get_app_config(appId=3950, includeSettings=false)` read. The deterministic reply discussed retained motion and illuminance, incorrectly answering an entirely different configuration/sensor-health question. No command-history, execution log or dated device event was consulted.

## Root cause

The existing Rule Machine configuration fast path intercepted `verify whether app 3950 actually issued an OFF command`. The general adaptive classifier did not recognise `verify` as an investigative verb, and the source-specific/telemetry planners did not match a focused historical command-verification question. As a result, the configuration-only presenter was invoked and appeared very fast, but had not investigated the requested event.

## Architectural correction

- Add a general named-app historical-execution intent contract. A request to verify/check/reconstruct whether an identified app issued a command, ran, triggered, sent a message or has execution logs must not be satisfied by reading only its current configuration.
- Enforce this contract **both** in Rule Machine fast-path eligibility and at the highest-priority read-only agent router. Provenance questions go to the evidence-capable model/tool loop even when they do not contain the usual words `investigate`, `why`, `diagnose`, or `telemetry`.
- Preserve the original quick deterministic path for ordinary current rule configuration, triggers, required expressions and linked sensor health. Preserve write-confirmation protections: this change authorizes no device commands, rule edits or management operations.
- Record `historical_rule_execution_routed` and `investigation_snapshot_shortcut_bypassed` for transparent diagnostics.

## Regression tests

Cover the exact app 3950/October 12 request, alternative historical app-command phrasings, explicit writes and unchanged current-configuration reads. A router-level asynchronous test checks that the historical question actually reaches the model/tool investigation path and does not execute the old single config read.

## Out of scope

A correctly routed model investigation may still end *unresolved* if historical event pages are truncated or app execution logs unavailable. No change to Ollama billing, free/paid selection or local budgets. This release does not yet solve pathological cloud-model latency or implement request cancellation. Both remain separate architectural priorities.
