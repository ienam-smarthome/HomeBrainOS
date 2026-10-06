# Hubitat MCP AI 0.16.113

## Canonical deterministic history tables

- Fixes the live 0.16.112 case where a safe model answer kept a rounded interval table such as `17s` and `3m` even though exact deterministic interval seconds were available.
- Replaces the first model-authored On/Off/Duration history table with the canonical table derived from `observedIntervals`.
- Uses the existing deterministic 24-hour time rendering and readable exact duration units such as `17 sec` and `2 min 50 sec`.
- Runs on the safe complete-window path as well as corrected answers, so an otherwise acceptable headline no longer lets rounded table values escape normalization.
- Preserves surrounding prose and unrelated Markdown tables.
- Adds regressions for the exact 0.16.112 Bathroom Light 1 table and for unrelated-table preservation.
- Canonicalisation is presentation-only; total duration arithmetic, semantic windows, and retained-history completeness logic are unchanged.
