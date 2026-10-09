# Hubitat MCP AI 0.16.125

## Changes
- Remove the duplicate `Hubitat returned N automation items` UI line above the searchable, collapsible inventory; preserve app counts in the answer.
- Distinguish a `hub_read_rules` response without structured rule entries from a verified empty Rule Machine installation. Record coverage as unavailable instead of asserting zero rules.
- Preserve a separate tool-failure explanation and explicitly state that individual rule execution remains unverified.
- Regression tests cover missing rule coverage and concise summaries.

## Scope and safety
- Reporting/UI-only changes, with no Hubitat writes.
- Determining a reliable supported MCP Rule Machine listing mechanism and action-level dependency diagnostics remains open in #725.
