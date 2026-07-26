# 0.10.139

## Deterministic named Rule Machine status

- Adds direct status queries for named Rule Machine rules and exact Rule IDs.
- Reports disabled, paused and active states separately from authoritative `hub_list_rules` data.
- Supports shortened names such as `status of fridge freezer rule` through safe candidate matching.
- Offers Pause or Resume actions based on the actual current state without sending a write automatically.
- Adds regression coverage proving paused, disabled and active states are not conflated.
