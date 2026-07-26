# 0.10.141

## Central named entity resolution

- Generalises the typed entity-resolution contract beyond devices to apps, Rule Machine rules and rooms.
- Adds one deterministic `NamedEntityResolver` for exact IDs, exact names, safe candidate ranking and ambiguity reporting.
- Makes app and rule controllers share the same resolver instead of maintaining separate name-matching implementations.
- Preserves exact-ID confirmation and blocks unsafe one-word fuzzy control candidates.
- Keeps shortened names such as `fridge freezer rule` as clarification candidates rather than exact write targets.
- Adds regression coverage for exact app resolution, shortened rule candidates, broad aliases and authoritative IDs.
