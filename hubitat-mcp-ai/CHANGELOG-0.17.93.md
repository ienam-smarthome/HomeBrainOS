# 0.17.93 — Safe explicit free quota paid fallback

- Adds disabled-by-default `ollama_free_quota_paid_fallback_enabled` to attempt one budget-reserved paid cloud model on the same account after a confirmed structured HTTP 402/429 free-tier exhaustion response.
- Does not interpret generic 429s, text-only errors, partial streams, timeouts, 401/403 or other users' account restrictions as exhausted free allowance.
- Does not rotate household keys, retry endlessly, change tool privileges, alter write confirmation or purchase Ollama credits.
- Needs vendor-confirmed error-code compatibility before relying on automatic switching in production: unsupported/ambiguous errors fail closed.
- Keeps existing locally configured fallback behavior and estimated USD ledger; vendor billed token usage may differ.
