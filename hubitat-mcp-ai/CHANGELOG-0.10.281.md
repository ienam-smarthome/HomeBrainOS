# Hubitat MCP AI 0.10.281

- Reject semantically invalid Rule Machine trigger and action shortcut specs
  before they reach confirmation or Hubitat.
- Enforce the upstream Certain Time wall-clock trigger contract, mapped switch
  `action` field, and complete `runCommand` custom-command contract.
- Reject ambiguous rules that combine multiple daily times with multiple
  actions; time windows must be submitted as two independently named atomic
  rules in one confirmation group.
- Direct rule authoring to a targeted label-filtered device lookup and verified
  command discovery instead of loading the complete device inventory.
- Revalidate these semantic invariants immediately before confirmed replay.
- Add regression coverage for the exact 0/2-trigger and 0/2-action payload that
  created the partial Tab S9 FE rule shell.
