# Hubitat MCP AI 0.10.222

## Authoritative device reads

- Prefetches one unfiltered live device snapshot for read-only device questions.
- Treats the short-TTL manifest as identity-only fallback, not live-state proof.
- Removes tool discovery from known device requests to avoid unnecessary model rounds.
- Labels evidence receipts by purpose so technical details distinguish authoritative
  state, identity manifests, discovery, and ordinary tool results.
