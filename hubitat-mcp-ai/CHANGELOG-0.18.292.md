# HomeBrainOS v0.18.292 — Stage 4N in-app Cloud AI Benchmark

**Manually triggered and synthetic-only. Uses the already-configured primary Ollama Cloud account.**

- Adds an isolated, read-only **Cloud AI Benchmark** section to the mobile WebUI. The user selects one fictional lighting, heating, ventilation, or history case and must tick the cloud allowance acknowledgment before a run can start.
- Sends exactly **one** bounded request to `https://ollama.com/api/chat` with the already-configured primary cloud credential/model. No new account, GitHub key, local fallback, paid-model selection, household-key failover, retries or MCP calls.
- The model writes up to three sentences referencing fictional Stage 4A facts. The host reconstructs typed citations, validates source binding, and hashes the full answer using Stage 4K. A structurally valid citation **does not** establish that the free-form prose is truthful.
- Shows actual model text, response time, selected model, fictional expected evidence limitations, and an explicit "independent review required" notice.
- Enforces same-origin JSON POST, explicit per-request confirmation, a single in-flight request, and a 90-second cooldown to limit accidental double taps. Neither prompt, key nor response is logged by the benchmark.
- New mock-only tests prove direct-cloud routing isolation, cooldown, invalid IDs, malformed replies, unverified physical claims, no tool calls, and no credential leakage.

**Safety limits:** This adds an intentionally billable *manual* API endpoint, not a background or scheduled job. It does not access live Hubitat/HA evidence or modify any device, planner, source collector, routing, or active publisher. It is not yet a statistically calibrated Claude-quality benchmark or semantic publisher approval. It cannot authenticate a user separately from Home Assistant ingress / existing network access. Install/update the add-on before the panel becomes available.

Rollback: install the previous add-on build or revert Stage 4N.
