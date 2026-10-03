# Hubitat MCP AI 0.16.101

## One-time cleanup rule discovery

- Fixes the live cleanup path that reported `Checked 0 rules` despite Rule Machine containing rules.
- Cleanup now invokes the gateway explicitly as `hub_read_rules` with `hub_list_rules`.
- Destructive cleanup requires an explicit authoritative `rules` collection before scanning or deleting anything.
- Missing/malformed list structure now fails closed with a visible list error instead of masquerading as a successful empty scan.
- An explicit empty `rules: []` result remains a valid zero-rule scan.
- Candidate extraction uses only returned rule IDs/names; existing exact one-time naming, grace-period, soft-delete, and future-rule protections remain unchanged.
