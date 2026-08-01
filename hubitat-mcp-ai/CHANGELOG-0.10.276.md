# Hubitat MCP AI 0.10.276

- Fix dynamic tool discovery to consume the upstream `hub_search_tools`
  `results[].gateway` wire contract while retaining the older `matches[]`
  compatibility form.
- Direct Rule Machine authoring requests through targeted discovery and the
  `hub_manage_rule_machine` / `hub_set_rule` path instead of falsely reporting
  that new rules cannot be created.
- Preserve confirmation-before-execution for Rule Machine mutations and add
  regression coverage for the reported Tab S9 scheduling request.
