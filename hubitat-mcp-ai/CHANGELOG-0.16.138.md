# HomeBrainOS v0.16.138 — balanced scheduler ownership candidates

## Improvements
- Corrected scheduler candidate rankings: app-prefixed and device-prefixed jobs are independently ranked instead of selecting a combined top ten which preferentially showed apps when all groups had one job each.
- Show the number of unique candidate IDs, key-derived scheduled entries, and top owner/handler combinations for each kind. All figures derive from the full structured job result, not a random raw excerpt.
- Distinguish three disjoint groups explicitly: rows containing authoritative owner IDs, rows containing only an unverified scheduler-key owner candidate, and rows with **no** candidate. Retain the existing `unattributedRows` metric as *not confirmed*, including candidate rows, for compatibility.
- Correct model-authored job tables that present `App` or `Device` as confirmed owner categories with only key-derived evidence; mark them as unverified candidates. A model's "Unattributed" aggregate handler totals are relabelled "Handler aggregate (owner unverified)" to avoid implying that those counts are disjoint from candidate rows.
- Compact scheduler evidence adaptively into a complete JSON first line within the existing 7,500-character packet cap, while preserving exact total, coverage and both candidate kinds.
- Tests reproduce the live 250-job result with 188 strict key candidates (118 device, 70 app), 62 with no candidate, the method table, and owner-label qualification.

## Safety
- No Hubitat rules, devices, apps, or schedules are changed.
- Key-derived numeric IDs remain unverified until matched against authoritative entity inventories. Shared next-run timestamps do not prove execution bursts, CPU contention or achievable savings. Full dependency and cost validation remain issue #733.
