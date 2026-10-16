# 0.17.92 — Opt-in paid Ollama routing and estimated credit reservations

## Changes
- Adds disabled-by-default cloud-model routing: free Gemma 4 for routine queries, DeepSeek V4.1 Flash for medium complexity, and configurable DeepSeek V4 Pro / GLM-5.3 for investigations.
- Adds hybrid, explicit manual and paid-first choices in Home Assistant add-on settings, without touching the existing secure secondary household-account configuration.
- Adds persistent, concurrent-request-safe, fail-closed **estimated** reservation accounting at `/data/ollama_paid_usage.json`; starts with illustrative $6.50 USD budget and does not auto-reload or purchase Ollama credits.
- Retains previously configured local/cloud ordering and fallback. Existing Hubitat mutation confirmation and tool permissions are unchanged.

## Limitations and verification
- Model routing is heuristic, and the selection does not prove superior HomeBrain diagnosis. A proper free-vs-premium benchmark is still required.
- The estimated reservation limit is **not an Ollama-side charge cap** or an exact measurement of billable token usage, particularly for model reasoning tokens or different provider billing. Keep Ollama auto-reload disabled and inspect actual usage.
- New unit tests cover routing, disabled-by-default, persistent-budget and corrupt-ledger protections. The full repository CI suite must pass prior to merging.
- No HomeBrain devices, Rule Machine automation, provider billing or passwords are changed by this release.
