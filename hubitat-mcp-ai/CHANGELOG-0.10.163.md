# Hubitat MCP AI 0.10.163

## Changed

- Consolidated authoritative membership, safe state merging, dashboard metrics,
  duplicate-name diagnostics and spoken-name resolution into
  `device_intelligence_catalogue.py`.
- Consolidated conservative per-session follow-up behavior into
  `conversation_context.py`.
- Removed `device_intelligence_catalogue_safe.py`,
  `device_intelligence_duplicate_safe.py` and `conversation_context_safe.py`.
- Generalized cluster analysis to distinguish sibling subclass chains from
  ordinary function composition.
- Updated architecture, contribution and single-add-on documentation.

## Validation

- Canonical catalogue and conversation-context behavioral regressions.
- Analyzer subclass, composition and allowlist regressions.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
