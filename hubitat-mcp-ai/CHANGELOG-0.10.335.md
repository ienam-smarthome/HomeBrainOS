# Hubitat MCP AI 0.10.335

- Omit the configured model from `/api/ask` response metadata when request metrics show that no model round participated.
- Keep model metadata for provider-backed requests and legacy outcomes where model participation cannot be determined.
- Add regression coverage for deterministic and model-backed response metadata.
