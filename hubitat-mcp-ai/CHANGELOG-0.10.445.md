# Hubitat MCP AI 0.10.445

- Canonicalize an action array mistakenly placed under singular `addAction` to `addActions` before validation and confirmation.
- Canonicalize a single action object mistakenly placed under plural `addActions` to `addAction`, with the same handling for trigger containers.
- Apply the same conservative normalization again during confirmed replay so queued payloads remain valid across an add-on restart or update.
- Preserve the original model payload and normalize only unambiguous container-shape swaps.
