# v0.18.28 — Free-by-default routing with optional Claude API paid provider

## Behaviour
- **Free (Gemma)** is selected by default in the HomeBrain web UI and is also the default `ChatRequest.model_tier` when callers omit a model tier. Free cannot escalate to a paid model from prompt text or due to Ollama quota exhaustion.
- Existing **Auto** remains an *explicit, non-default* hybrid choice for compatibility; its Ollama paid-routing rules may still charge. Selection is request-scoped; no browser persistence.
- **Paid · DeepSeek Pro (Ollama)** remains the existing per-turn strict-paid option and uses the existing Ollama credits/guard.
- **Paid · Claude (Anthropic API)** is a new separate per-turn explicit choice. It calls Anthropic's official HTTPS Messages API using the configured Anthropic API key. Claude does NOT run through Ollama, consume Ollama credits or fall back to Ollama/local models on errors. Billing and account controls belong to Anthropic. It is disabled in the UI until the key is configured.
- Configuration: `anthropic_api_key` (masked Home Assistant add-on password field; empty by default), `anthropic_model` (defaults to `claude-sonnet-4-6`). No keys are returned from `/api/status`. Never paste keys into chat or include them in debug dumps.

## Technical details
Claude's Messages API differs from Ollama's API: system instructions are top-level, function schemas require `input_schema`, Claude returns `tool_use` blocks and expects exact `tool_result` IDs. The new opt-in `AnthropicMessagesTransport` translates model messages, declared tools, and tool results while leaving Hubitat MCP execution, permissions, native Groovy analysis, source verification, and write confirmations in the existing HomeBrain executor.

Every Claude call is an explicit paid model round. Provider errors, missing key, rate limits and cancellation are fail-closed without automatic cross-provider retries. Request-local contextvars keep choices isolated across browser sessions and prevent model-generated tool output from authorizing provider changes. Usage reports show Anthropic as the provider and identify its account as the billing authority.

## Validation
Pytest fixtures exercise default Free routing, explicitly opted-in legacy Auto, separate paid providers, tool schemas, native tool call IDs and results, no invented tool provenance, partial/missing-tool safeguards, provider and billing metadata, authentication failures, HTTP errors, cancellation, and absence of paid cross-provider fallback. Live call validation requires **the user's own Anthropic API key** after add-on upgrade; tests never make a real billable Claude request.

## Release
Merge only after all three required CI workflows pass. No hub setting or device state changes.
