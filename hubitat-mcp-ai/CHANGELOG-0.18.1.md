# 0.18.1 — Explicit paid-model routing reliability

- Preserve the original, explicit user intent across host-added user-role prompts in evidence-rich investigations. Tool output and synthetic guidance cannot independently authorise spending.
- When Manual paid routing is enabled and the user explicitly requests a paid model, prefer authorised cloud selection over local-first routing; retain local fallback if cloud fails.
- Record request-local model-selection and credit-guard decision counters, and surface `paid_routing` details when the user explicitly requested paid review. The API now discloses when the actual model rounds did not use paid DeepSeek or GLM.
- No paid routing is enabled by default; users must explicitly enable it and provide an appropriate local estimated budget. Ollama prepaid credits are not the same as HomeBrain's budget guard.
- Adds regression tests for host instruction masking, forged synthetic paid requests, credit guard reservations and final model disclosure.

This release does **not** make provider credit claims, enable automatic paid fallback, or change read/write confirmation policy. It does not guarantee paid model invocation when local spending permissions are disabled or credits/budget are unavailable.
