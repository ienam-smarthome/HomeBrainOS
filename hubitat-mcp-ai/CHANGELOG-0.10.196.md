# Hubitat MCP AI 0.10.196

## Canonicalize the large live module owners

- Renames the 1,500-line Hubitat Rule Machine owner to
  `automation_rule_workflow_hubitat.py`.
- Renames the 2,800-line guarded backup, write and repair owner to
  `automation_rule_workflow_recovery.py`.
- Preserves every public workflow class, installer and safety-stage MRO while
  switching all production and regression imports to the canonical owners.
- Renames the remaining power, system and weather `_safe`/`_v2` modules and
  removes three dead tracked `.backup` copies.
- Adds repository hygiene tests preventing patch/version suffixes and backup
  source copies from returning.
- Prevents a selected device named `Battery` from making ordinary low-battery
  prose fail the AI grounding guard.
- Includes verified non-light devices that are on in whole-home semantic
  summaries so active appliances are no longer hidden from synthesis.
