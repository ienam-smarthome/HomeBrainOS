# Hubitat MCP AI 0.16.98

## Internet-group local identity matching

- Scheduled Internet access remains strictly scoped to the authoritative Hubitat `Internet` room/group or an explicit configured Internet alias.
- Adds a conservative room-local token-subset matcher before the existing fuzzy fallback. It tolerates natural token reordering and compact/camel model labels such as `M6 Ultra PC` versus `Block PC-NucBox-M6Ultra`.
- Every identifying token supplied by the user must occur in the candidate identity after bounded normalization; extra candidate tokens are allowed.
- Multiple matching Internet controls remain ambiguous and are surfaced for clarification rather than guessed.
- The global device resolver is unchanged.

## Identity-cache latency

- Scheduled Internet resolution now reuses `peek_device_identities()` when a complete identity snapshot is still within the identity TTL.
- It falls back to one bounded manifest/identity refresh only when no fresh structural identity cache exists.
- This avoids expiring the short live-device cache forcing a multi-second manifest refresh when structural room/name/capability identity is already fresh.
- The selected control surface is still re-read by authoritative label and its real `on`/`off` Switch command is verified before a Rule Machine proposal is queued.

## Regression coverage

- `M6 Ultra PC` uniquely resolves to `Block PC-NucBox-M6Ultra` inside the Internet room.
- A warm identity cache prevents a manifest refresh on that path.
- `Tab S9 FE` remains ambiguous when both `Block Enamul-s-Tab-S9-FE` and `Block Tab-S9-FE` satisfy the same scoped token identity.
