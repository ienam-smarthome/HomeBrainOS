# Hubitat MCP AI 0.10.282

- Replace text-detected confirmation buttons with structured backend
  `confirmation_required` and `confirmation_count` state.
- Reject a bare confirmation when no action group is pending; no model call or
  Hubitat write occurs.
- Detect model claims such as “please confirm”, “ready to queue”, and “have
  queued” when no structured write exists, and require the model to submit the
  actual tool-call group instead.
- Add `homebrain_resolve_device`, a bounded targeted resolver that tries space,
  hyphen, and distinctive numbered-token label filters before deterministic
  matching. It does not load the complete device inventory.
- Require the targeted resolver before accepting a model claim that a named
  device cannot be found.
- Add regressions for `tab s9` resolving to `Block Tab-S9-FE` (device 6916),
  false confirmation buttons, missing pending sessions, and ungrounded queue
  claims.
