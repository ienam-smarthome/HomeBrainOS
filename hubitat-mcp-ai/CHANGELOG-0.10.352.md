# Hubitat MCP AI 0.10.352

## Changed

- **Default configured model switched from `gemma4:31b` to
  `qwen3-coder:480b-cloud`.** Requested after live testing surfaced a
  concrete failure mode: with `gemma4:31b`, a scheduling request that fell
  through to the generic model tool-calling loop burned 7 model rounds and
  8 tool calls trying (and failing) to find the right MCP gateway, then
  fabricated a plausible-sounding "success" message instead of admitting
  it couldn't complete the task (see 0.10.346/0.10.347). `gemma4:31b` sits
  in the small-to-mid tier of Gemma's own published size range (E2B-E27B);
  `qwen3-coder:480b-cloud` is Ollama Cloud's largest available model and is
  specifically noted for strong tool/function-calling performance.

  This is a configuration change, not an architecture change. HomeBrainOS
  already supported swapping the model via `ollama_direct_cloud_model`
  (Ollama Direct Cloud, hitting `https://ollama.com` directly) -- no new
  code path was needed. `ProviderTokenEstimator` already had a `"qwen"`
  profile (distinct byte-per-token estimate from `"gemma"`) before this
  change, so token budgeting for context management adjusts automatically
  with no additional work.

  The deterministic safety layer is unchanged and applies identically
  regardless of which model is configured: `RuleAuthoringService` still
  compiles recognised schedule phrasing itself rather than letting any
  model -- weak or strong -- invent `hub_set_rule` JSON, and every
  Rule Machine write still goes through `rule_machine_proposal_error`
  validation and requires explicit user confirmation before it reaches the
  hub. What a stronger model can improve is conversational tool-use
  reliability in the *generic* tool-calling loop (the fallback path for
  anything the deterministic grammar doesn't recognise) -- fewer wasted
  discovery rounds, less risk of giving up and fabricating a result instead
  of reporting failure honestly.

  Updated everywhere the old default was hardcoded: `config.yaml`
  (`ollama_direct_cloud_model` and `ollama_cloud_model` options),
  `app.py` (in-code options default and the final inline fallback),
  `mcp_agent_orchestrator.py` and `chat_transport.py` (constructor
  defaults), and the example config block in `hubitat-mcp-ai/README.md`.

  If you've already set `ollama_direct_cloud_model` explicitly in the
  add-on's own configuration UI, that value takes precedence over this
  default and nothing changes for you automatically -- update it there if
  you want to switch.

## Validation

- `python -m pytest -q` -- 569 passed, no changes needed (existing tests
  pass explicit model-name fixtures rather than asserting on the app-wide
  default, so none were coupled to the old value).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.352.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Verified `ChatTransport`'s existing `-cloud` suffix-stripping logic
  produces the correct wire model name (`qwen3-coder:480b`) for the new
  default before sending any request to the cloud API.
