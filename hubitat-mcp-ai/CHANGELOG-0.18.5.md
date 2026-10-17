# 0.18.5 — Installed Groovy source-code evidence

- Prevent the deterministic Rule Machine configuration/sensor-health presenter from intercepting requests that explicitly ask for the Groovy source of a named installed app.
- Route these requests to a bounded read-only Groovy-source investigator, before model/snapshot planning.
- Discover source read operations from the live MCP tool schema and hub_search_tools results; do not invent an unadvertised sub-operation.
- Use instance-to-code ID metadata when available. An installed app instance (e.g., app 4019) must not be assumed to have source code ID 4019. A user-reported source code ID is not hard-coded.
- Attempt bounded multi-chunk source retrieval (up to four chunks / 250k characters). Preserve a SHA-256 and excerpts with retrieval-relative line numbers, not full code in UI/evidence receipts.
- State clearly when an operation is missing, code-ID metadata is unavailable, raw source was not returned or full-source coverage is unverified. No deductions about absent methods or timer persistence are allowed without implementation evidence.
- Add regressions for the exact Livingroom app 4019 source question, code ID metadata, a three-chunk source response, a direct MCP source tool, missing source operations, and preservation of ordinary current-status routing.

**Important:** The actual upstream MCP source tool's operation and argument schema are deployment-specific and cannot be verified from the GitHub project alone. This version's live test must confirm discoverability and raw-source retrieval. No Hubitat automations are changed. File Manager caches created by upstream source tools are outside HomeBrain's control.
