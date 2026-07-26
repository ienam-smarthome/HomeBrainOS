# Hubitat MCP AI 0.10.157

## Changed

- Consolidated the base HomeBrain renderer, mobile dashboard, clipboard
  fallback and HTTP error handling in `webui.py`.
- Preserved the public `render_homebrain_page`, `render_page`,
  `patch_clipboard`, `patch_http_errors` and installer entry points.
- Retained the existing entrypoint wrapper order and kept feature-specific UI
  patchers as separate maintained capabilities.

## Removed

- Removed three superseded sibling-only modules: `webui_homebrain.py`,
  `webui_clipboard_safe.py` and `webui_http_safe.py`.

## Validation

- AST equivalence checks for all five moved definitions.
- Focused renderer, clipboard, HTTP safety and Web UI regression suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
