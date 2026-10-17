# 0.18.19 — Strict Paid-only DeepSeek, no HomeBrain budget

## User-requested behaviour
- **Free:** Remains strictly the configured free model; no automatic paid upgrade.
- **Auto:** Retains hybrid routing (complex questions may incur paid-model charges).
- **Paid:** Requires DeepSeek Pro for every model round. If the paid provider is disabled or unavailable, return a clear failure rather than silently continuing the investigation on Gemma or a local model.
- **Remove the HomeBrain budget:** `ollama_paid_budget_usd` no longer appears in the add-on configuration. Production passes no local cap and neither reads nor updates the old `/data/ollama_paid_usage.json` reservation ledger. Existing ledger data is preserved but ignored. There is no need to manually raise or reset HomeBrain's estimated $3 ceiling.

## Billing distinction
Actual spending remains controlled by Ollama account available credits, payment terms and auto-reload. HomeBrain cannot read the live Ollama balance and does not impose a second billing limit. Keep Ollama auto-reload OFF if a fixed prepaid balance is intended. Auto/hybrid mode can still spend credits when it selects DeepSeek.

## Diagnostics
- Every request with recorded model rounds reports `model_usage` identifying participating model names and paid/free round counts, including automatic hybrid routing.
- A separate model-continuity object is produced when Auto mixes free and paid rounds.
- The existing `paid_routing` shape remains backward-compatible for explicit Paid requests.
- A selected Paid request whose model routing is disabled returns a clear failure. An Ollama HTTP 402 while in strict Paid mode returns a payment-required explanation, never a free-model success.
- The HomeBrain Ask interface shows actual participating model counts alongside the answer; the selector describes provider-account-only billing.

## Compatibility and scope
The Python `PaidCreditGuard` class retains its optional finite-budget branch for isolated legacy tests and callers explicitly passing a finite number, but the production add-on no longer configures or uses that branch. No devices, Hubitat rules, credentials, permissions or existing confirmation policy are changed.

## Tests
Regress seven consecutive DeepSeek Paid rounds, unavailable paid route fail-closed, provider error without Gemma/local fallback, legacy ledger ignored without deleting data, Auto mixed-model reporting, unchanged Free protection, and add-on budget field removal.

GitHub CI must pass before merge; live Home Assistant validation remains separate.
