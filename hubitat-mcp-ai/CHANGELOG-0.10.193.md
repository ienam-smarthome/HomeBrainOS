# Hubitat MCP AI 0.10.193

## Catalogue live routes and centralize MCP safety metadata

- Describes major live routes as structured capabilities with required MCP
  tools, slot schemas, safety classes and runtime identifiers.
- Makes passive route agreement evidence accurate by separating comparable,
  agreeing, disagreeing and unmapped requests.
- Preserves MCP output schemas and annotation hints for planning, diagnostics
  and safety classification.
- Reports safety coverage across visible and gateway-contained MCP tools.
- Uses one conservative destructive-call confirmation classifier for AI tool
  execution.
- Invalidates cached state after device, rule, app, room, variable, dashboard,
  code, hub and direct-gateway mutations.
- Recognizes natural log-purpose clauses such as `to see if there are any
  issues`, keeping them on the authoritative 24-hour Hubitat log scan.
