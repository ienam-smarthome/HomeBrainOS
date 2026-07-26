# 0.10.142

## Remove redundant Rule Machine matcher

- Removes the legacy `named_rule_match_guard` from runtime composition.
- Keeps the central `NamedEntityResolver` as the sole app and Rule Machine candidate-ranking layer.
- Preserves exact-ID confirmation, safe shortened-name clarification and the separate disable guard.
- Adds composition-order regression coverage so the redundant matcher cannot be reintroduced accidentally.
