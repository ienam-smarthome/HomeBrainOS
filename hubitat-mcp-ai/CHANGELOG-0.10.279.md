# Hubitat MCP AI 0.10.279

- Run one bounded capability discovery with the unchanged original request
  before the first non-conversational model turn, and immediately declare any
  returned known gateways.
- Prevent model-selected read searches such as `read Rule Machine rules` from
  hiding a creation gateway relevant to the actual request.
- Treat only an empty no-confirm `hub_set_rule` operation envelope as a
  read-only schema probe. A populated no-confirm proposal is now correctly
  classified as a sensitive write and queued for HomeBrain confirmation.
- Tell the model explicitly that an existence report does not complete an
  original create or edit operation when authoring capability was discovered.
- Preserve the verified post-confirmation execution and fail-closed completion
  reporting introduced in 0.10.278.
