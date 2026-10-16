# 0.17.99 — Required read for named automation status

- Exact app-ID current-status queries bypass LLM tool discovery and execute read-only `hub_get_app_config` through the MCP client after confirming availability.
- A missing tool, failed read or unparseable response is reported as incomplete, not fabricated as verified app status.
- Bounded configuration excerpts are returned only after a successful read; no Hubitat automation is changed.
- Adds regression tests for app 4019, missing tools and source-call execution. Free/paid Ollama model policies remain unchanged.

Limitations: This PR only improves required-source execution for targeted app-status questions. It does not guarantee complete historical causality, all configuration fields or automated paid-model escalation.
