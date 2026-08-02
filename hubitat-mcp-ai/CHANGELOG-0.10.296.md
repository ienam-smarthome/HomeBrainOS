# Hubitat MCP AI 0.10.296

## Changed

- Wired `api_response_builder.build_agent_response` into the live `/api/ask` endpoint.
- Added request-local privacy-safe metrics to the returned API payload when available.
- Preserved the existing route, intent, message, choice, confirmation, evidence, model, timing, and version fields.

## Safety

- Evidence and metrics are deep-copied by the response builder before returning them.
- Prompt text, query text, session IDs, and request IDs are not added to the response.
- Legacy outcomes without metrics continue to return an empty metrics object.

## Tests

- Added endpoint wiring checks for the stable serializer and runtime metadata arguments.
