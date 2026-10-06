# Hubitat MCP AI 0.16.110

## Duplicate history presentation repair

- Fixes the live 0.16.109 case where a deterministic repaired duration answer was followed by a second model-generated On/Off/Duration table and repeated history note.
- Keeps the deterministic canonical history table as the single interval presentation.
- Removes only later duplicate temporal-history tables and their matching retention/completeness caveat.
- Preserves unrelated analysis paragraphs and unrelated Markdown tables after a localized duration repair.
- Keeps the 0.16.109 natural duration units, 0.16.108 table layout, and 0.16.107 retained-page completeness semantics unchanged.
- Adds regressions for the exact Bathroom Light 1 duplicate-table shape and for preservation of an unrelated analysis table.
