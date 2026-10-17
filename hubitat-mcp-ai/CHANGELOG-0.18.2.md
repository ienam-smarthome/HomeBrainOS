# 0.18.2 — Transparent local paid-budget guard decisions

- Explicitly requested paid-model calls now report why the local estimated-credit reservation was rejected: proposed round exceeds the remaining local budget, corrupt ledger, unavailable ledger storage, disabled routing or zero local budget.
- Exposes only rounded estimated amounts and a decision status in `metrics.paid_guard` and `paid_routing.local_guard` when a paid request is made. No API keys, raw prompts, filesystem paths, or Ollama billing information appear in these diagnostics.
- Distinguishes prepaid Ollama credits from HomeBrain's conservative cumulative **estimated** reservation ledger. No provider balance reads, changes to credit balance, automatic recharge, ledger reset, or permission bypass.
- Corrupt, negative, or non-finite ledger totals fail closed rather than permitting extra spending. Existing ledger data is preserved when a round is blocked.
- Adds regression tests for insufficient first-round allocation, exhausted cumulative budget, corrupted ledger, successful reservation and API status.

This is observability, not a cost-cap bypass or confirmation that Ollama credits are exhausted. Estimates intentionally remain conservative.
