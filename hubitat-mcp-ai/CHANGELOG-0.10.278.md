# Hubitat MCP AI 0.10.278

- Translate an approved HomeBrain confirmation into the nested `confirm:true`
  required by the upstream `hub_set_rule` apply contract.
- Treat no-confirm Rule Machine operation envelopes as read-only schema probes,
  allowing the model to inspect the current trigger/action shape before it
  proposes a sensitive write.
- Report confirmed Rule Machine completion deterministically from structured
  success, rule ID, partial, and health fields instead of asking the model to
  guess whether the write succeeded.
- Refuse to claim success for failed, partial, unhealthy, or ID-less rule
  results and identify the affected rule in the response.
- Keep generic device-filter results inside the tool loop so an irrelevant
  filter call cannot terminate a still-unfinished automation request.
- Add regression coverage for successful two-rule confirmation, failed writes,
  schema-probe classification, and post-filter continuation.
