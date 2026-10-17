# v0.18.29 — Safe Claude API HTTP diagnostic reporting

## Live failure
After upgrading to v0.18.28, the HomeBrain UI returned:

```json
{"success": false, "route": "error", "message": "Request failed: The model provider returned an HTTP error. Hubitat and MCP may remain available."}
```

The backend translated almost all `httpx.HTTPStatusError` exceptions into this same generic HTTP 502. That conceals upstream provider status and error class, preventing an operator from distinguishing authentication, billing, rate limiting, unavailable model or incompatible tool/message format. **We cannot establish the original upstream error code from this UI output.** The configured default `claude-sonnet-4-6` is a valid Anthropic model identifier, so replacing that model without evidence is not indicated.

## Fix
- For requests explicitly using `model_tier=claude`, classify Anthropic HTTP 400, 401, 402, 403, 404, 413, 429, 5xx and 529; preserve the upstream HTTP status in HomeBrain's response (apart from unrecognized statuses).
- For HTTP 400, inspect only a bounded upstream error message **internally** to assign a limited category: tool transcript/result, tool schema, message format, model parameter or unknown request validation. Return a stable explanatory category and allowlisted provider error type **without ever echoing the raw error body**.
- Return safe numeric `Retry-After` for rate limits. Log the HTTP status and diagnostic category only, without exception traceback or provider response body that might contain private evidence or API secrets.
- Also distinguish Ollama Cloud HTTP 400/401/402/403/404/413/5xx failures, especially the Free-default route; never echo the raw upstream body. Do not mislabel either provider as a Hubitat/MCP outage. Preserve strict explicit Claude routing; no paid/free provider fallback, retry or Hubitat writes.
- Support staff can diagnose the root cause from the new safe `HTTP NNN; type=X; category=Y` result. No live billing/API call was made during these tests.

## Validation
HTTP error simulation and endpoint tests cover bad Anthropic tool schema (400), authentication (401), billing (402), model unavailable (404), rate limit (429), provider overloaded (529), malicious body redaction and sanitized Retry-After; all three CI workflows must pass before merge.

## Next
Install 0.18.29. Reproduce **one low-cost simple Claude question** such as "Say OK" and copy the new sanitized error message; no API key. If it succeeds, test an evidence read to isolate tool-schema/transcript failures. Do not claim the underlying provider failure has been fixed until that live output is collected.
