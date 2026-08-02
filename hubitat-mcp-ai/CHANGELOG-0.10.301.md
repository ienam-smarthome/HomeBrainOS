# Hubitat MCP AI 0.10.301

## Added

- Record cumulative remote Hubitat MCP duration at the `ToolExecutor` boundary.
- Include both successful and failed remote calls in the request-local MCP timing.
- Add focused regression coverage for cumulative, failed, and local-adapter paths.

## Safety

- Local adapters are excluded from MCP latency so the metric is not a mixed execution duration.
- Timing labels remain fixed and privacy-safe; tool names, arguments, prompts, device names, and session identifiers are not used as metric dimensions.
- Tool execution, evidence recording, grounding, and confirmation behaviour are unchanged.
