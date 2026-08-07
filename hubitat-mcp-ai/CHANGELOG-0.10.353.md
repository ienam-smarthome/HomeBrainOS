# Hubitat MCP AI 0.10.353

## Fixed

- **Reverted the 0.10.352 default model change — `qwen3-coder:480b-cloud`
  does not exist on Ollama Cloud and broke every request, not just
  scheduling.** Live testing immediately after 0.10.352 showed every
  request, including basic dashboard shortcuts like "which lights are on,"
  failing with `Client error '410 Gone' for url 'https://ollama.com/api/chat'`.

  This was a real mistake: the 0.10.352 change picked `qwen3-coder:480b-cloud`
  based on a general web search result, without verifying it against
  Ollama's own current model catalog first. Checking `ollama.com/search?c=cloud`
  directly afterward showed the current cloud lineup does not include
  `qwen3-coder` at all -- HTTP 410 Gone specifically means a resource
  that used to exist and was permanently removed, consistent with the tag
  having been retired since whatever source described it as available.

  Reverted every default changed in 0.10.352 (`config.yaml`, `app.py`,
  `chat_transport.py`, `mcp_agent_orchestrator.py`,
  `hubitat-mcp-ai/README.md`) back to `gemma4:31b-cloud` -- verified this
  time directly against Ollama's own model page
  (`ollama.com/library/gemma4`), which explicitly documents
  `ollama run gemma4:31b-cloud` under "Ollama's cloud" as a currently live
  model.

## Context

- If you already applied 0.10.352 and set `ollama_direct_cloud_model` to
  `qwen3-coder:480b-cloud` in the add-on's own configuration UI, that
  saved value overrides this code-level revert and your assistant will
  keep failing until you change it back yourself. Set both
  `ollama_direct_cloud_model` and `ollama_cloud_model` to
  `gemma4:31b-cloud` in the add-on config directly -- this is the same
  precedence behaviour documented in 0.10.352's own changelog.
- Lesson taken for future model-default changes: verify a model's current
  availability directly against the provider's own live catalog page
  before configuring it as a default, not from a general web search
  result alone. A stronger tool-calling model may still be worth trying
  in the future, but the next attempt will be checked against
  `ollama.com/search?c=cloud` directly first.

## Validation

- `python -m pytest -q` -- 569 passed, no test changes needed.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.353.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Verified `gemma4:31b-cloud` is a live, current Ollama Cloud model via
  `ollama.com/library/gemma4` directly (not a search snippet) before
  reverting to it.
- Verified `ChatTransport`'s existing `-cloud` suffix-stripping logic
  produces the correct wire model name (`gemma4:31b`) for this reverted
  default.
