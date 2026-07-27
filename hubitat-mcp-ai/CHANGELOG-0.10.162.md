# Hubitat MCP AI 0.10.162

## Changed

- Added an exact `ollama_agent` intentional-layer allowlist to
  `scripts/analyze_clusters.py`.
- Reclassified the documented `ollama_agent_fast` and
  `ollama_agent_inference` layers as live architectural components.
- Kept other sibling-only layers classified as suspect and disconnected
  allowlisted modules classified as orphaned.
- Documented the analyzer policy alongside the maintained four-layer Ollama
  inheritance chain.

## Validation

- Analyzer allowlist and negative-case regression tests.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
