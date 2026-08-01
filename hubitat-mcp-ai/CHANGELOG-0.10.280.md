# Hubitat MCP AI 0.10.280

- Align Rule Machine authoring with the upstream gateway contract: put `name`,
  `addTrigger(s)`, `addAction(s)`, and `bestPracticeKey` directly inside the
  `hub_set_rule` gateway `args` object.
- Remove the incorrect `operation/create/args` envelope from the system prompt,
  tests, effect classification, and confirmation path.
- Treat an empty management-gateway call and documented
  `addTrigger`/`addAction` `{discover:true}` requests as read-only schema probes.
- Declare `hub_get_tool_guide` in the bounded initial registry and direct rule
  authors to its live `best_practice_reference` and `set_rule_reference`
  sections instead of relying on a frozen local approximation.
- Reject incomplete, empty, already-confirmed, or invented `hub_set_rule`
  proposals before confirmation. The structured validation error returns to
  the model for correction; no action is queued or executed.
- Revalidate queued Rule Machine payloads immediately before replay as a final
  fail-closed boundary.
- Add regression coverage for the exact malformed payload observed after the
  Tab S9 FE confirmation and for corrected two-rule scheduling proposals.
