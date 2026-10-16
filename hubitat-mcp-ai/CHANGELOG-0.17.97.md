# 0.17.97 — Evidence-first verification

- Adds privacy-safe, read-only deduplicated command-event facts extracted from successful MCP evidence receipts.
- Corrects explicit false claims that no command occurred on a date when that date's command was read, while refusing to infer that a separate light activation has been proved.
- Exposes conflicting lockout-duration claims (persisted vs app summary) without silently choosing one or writing to Hubitat.
- Adds structured `evidence_validation` to API answers, with contradiction types only, not prompt or credential data.
- Includes regression tests using the real Bedroom 1 12 October command and Livingroom 30/300-minute discrepancy.

**Not yet included:** bounded automatic DeepSeek re-reasoning based on evidence contradiction. The current paid routing and budget settings are unchanged. The new validation is deterministic and has no additional Ollama cost.
