# Hubitat MCP AI 0.10.277

- Add output-side capability grounding so an AI-generated limitation triggers
  one bounded host discovery search using the unchanged original request.
- Prevent irrelevant discovery queries, existing app-name matches, or model
  assumptions from being presented as proof that a Hubitat operation is
  unsupported.
- Return a neutral no-action result when known gateways were exposed but the
  model still fails to produce a valid structured call.
- Preserve tool-call-driven effect classification and confirmation for every
  recovered mutation, with regression coverage reproducing the reported Rule
  Machine denial after a `list apps` search.
