# Hubitat MCP AI 0.10.142

## Changed

- Removed the obsolete `named_rule_match_guard` runtime installation.
- Kept `NamedEntityResolver` as the single runtime matcher for Hubitat apps and
  Rule Machine rules.
- Added an architecture regression preventing the legacy matcher from being
  reintroduced into `entrypoint.py`.

## Validation

- Repository layout validation.
- Blocking release gate.
