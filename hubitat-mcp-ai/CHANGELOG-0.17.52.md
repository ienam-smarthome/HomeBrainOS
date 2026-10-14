# HomeBrain 0.17.52 — opt-in cross-domain MCP task planning (phase 1)

## Motivation

HomeBrain already has native MCP function calling, live gateway discovery, typed
device control, and grounding/confirmation safeguards. However, its injected
skill guidance is normally selected by request keywords and its initial remote
tool search uses the whole user request. This can miss the needed native tool
and encourage narrowly hardcoded paths for paraphrases.

## Changes

- Add `GeneralTaskPlanner` and a strict, bounded semantic task contract:
  objective, domain, read/investigate/write *advisory* mode, skill domains,
  live-tool discovery queries, and evidence goals.
- Enable skill guidance selected from validated plan domains, not keywords.
  Includes device, automation, diagnostics, hub/room, integration, and code.
- Let the model's specific capability search phrase seed `hub_search_tools`
  instead of searching the user's entire message. Remote tool registry,
  discovery schema, Read/Write gates and confirmation remain authoritative.
- Keep all existing deterministic fast paths, live evidence checks, native rule
  write protections, and model fallback intact.
- Add a disabled-by-default add-on option:
  `general_task_engine_enabled: false`. This phase is not a replacement for
  the existing agent, and enabling it costs one additional planning model call
  on requests reaching the general MCP path.
- Add read-only simulated regression tests for semantic skill selection,
  multi-domain requests, invalid planner outputs, and provider failure.

## Limitations and next steps

- Phase 1 does **not** replace the existing causal handlers, rule authoring
  compiler, or final-answer validators.
- Skill selection is semantic, but the existing hardcoded handlers may still
  intercept a request before the new planner runs.
- Tool discovery and all writes still use the existing bounded MCP loop and
  runtime confirmation semantics. The plan does not authorise execution.
- Completion is still enforced by the existing grounded final-answer path;
  a general typed completion evaluator and full native-rule compiler are future
  milestones.
- Requires CI, deployed add-on smoke testing and read-only live side-by-side
  evaluation before the new mode should become the default.

No new Hubitat device, app, room, or automation changes are performed by
installing this release with the feature flag off.
