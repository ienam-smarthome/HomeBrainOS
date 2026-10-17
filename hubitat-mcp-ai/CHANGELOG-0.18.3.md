# 0.18.3 — Safer historical intent and concise tool-free technical answers

- Correct a live regression: a user question beginning `Use paid model. Why did Bathroom Light 1 turn on?` must be classified as a **read-only investigation**, not as an instruction to turn on a device. The same routing-prefix normalization applies to the existing investigative/causal prefixes. Explicit trailing write requests retain their write classification and confirmation gates.
- Introduce a strictly opt-in fast path for static technical explanations with an explicit instruction not to use Hubitat/MCP tools. It calls Ollama with **zero tools and only one model round**, without even performing MCP discovery. Live state, devices, named app IDs, historical events and state-changing requests are excluded.
- An explicit paid-model instruction still respects Manual routing and existing prepaid/estimated credit guards. No automatic paid escalation or budget changes.
- Regression tests cover a real Bathroom Light diagnostic, mixed write requests, rejection of live questions and a stubbed one-round response with no MCP calls.
- **Not in this patch:** deeper inspection of custom Groovy source when MCP returns no source. No code-reading claim is made in the absence of source evidence.

All Hubitat tools remain read-only for these two improved pathways; no device or automation writes are introduced.
