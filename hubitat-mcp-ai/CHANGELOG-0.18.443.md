# HomeBrainOS 0.18.443 — Autonomous Evidence-First Agent, Phase 1

## Why this is a new architecture milestone

A real read-only v0.18.441 bathroom humidity question requested the last
measured value above 70%, the first later reading strictly below 60%, and
their elapsed time. Claude reported 14:25 74% → 18:26 59% (4h 1m between
observed samples), but underlying Claude MCP event receipts were not supplied.
HomeBrain spent seven model rounds and six tool calls resolving/browsing
identity and current state; the event-history tool was never called. Its
answer truthfully reported missing device history, but failed to answer a
question for which an installed read-only tool was available. This is a
general evidence-planning/completion failure, not a bathroom-specific rule.

## Phase 1 implementation

- Turn on the **existing model semantic task planner** for
  non-conversational read-only requests by default. Write/confirmation
  requests do not gain any new planner authority, and the option remains
  configurable for rollback. The model may propose required evidence
  classes and matching read-only source operations.
- Add model-proposed `readRequests` for the existing safe
  `homebrain_device_history` adapter. The model supplies
  `name`, `attribute`, `hours_back` and `limit`. The host
  validates the known tool name, argument types and native bounds,
  installed tool effect and request read-only scope. The existing MCP
  resolver must independently verify the name, and the host executes the
  read through the existing evidence recorder. Returned events (or a real
  failure/empty response) are supplied to the model for grounding;
  proposed model requests are never treated as facts. This is usable for
  arbitrary event-bearing device attributes, not hardcoded room or values.
- The autonomous read-only reasoning profile no longer uses soft
  8/12/18-call or 3/5/7-read-round stopping budgets. It relies on the
  outer operational guard, duplicate-call prevention and actual verified
  source progress.
- Remove per-investigation short 3/6-round cutoffs in autonomous read
  mode; allow source checkpoint proposals only after *new successfully
  scoped read evidence*, without the arbitrary three-offer cap.
- Permit all positively identified **exact MCP operation** discovery
  results instead of truncating to the first two. Retain the fuzzy
  search top-two relevance filter for unrelated broad hits.
- Honour the configured investigation tool-view capacity rather than
  an extra hardcoded 32-schema limit. Increase the **configurable emergency**
  overall tool-round ceiling from 9 to 18; this is still not a promised
  18-round execution or a wall-time quality target.

## Intentionally retained safeguards

- Hard overall request deadline (default 180s) and 30s per-model-read
  cancellation, MCP concurrency/rate limits, provider/account quotas,
  finite schema/result windows and optional user overrides.
- Device identity validation, source evidence origin checks, read-only
  permission enforcement, write confirmations and Rule Machine authoring
  guards. No new autonomous writes or external background tasks.
- At most four distinct proposed local device-history results per
  planning step, with native history service time/row bounds; if older
  source periods cannot be proven, the assistant must report the gap.
- Normal status/control latency remains independently measured; complex
  investigations have no fixed speed acceptance target.

## Honest scope and next phases

Phase 1 creates model-led first-source retrieval but does not yet provide
generic guaranteed numerical time-series calculations, full MCP source
pagination, model-independent proof requirements for all tool types,
continuous learning, or a verified Claude-level first-answer rate.
These belong to Phases 2–4 in
[Autonomous Agent Roadmap](../docs/HOMEBRAIN-AUTONOMOUS-AGENT-ROADMAP.md).
No model fine-tuning, new paid route or Hubitat/Home Assistant/Router
configuration was performed.

Synthetic tests verify read proposal admission, anti-write/anti-ID
validation, multi-device reads, duplicate source progress, discovery and
the removal of arbitrary read-only budgets; they do not substitute for
source-real evidence. Run one original threshold question plus held-out
history tasks with complete Technical JSON and compare actual source
reads, arithmetic and first-answer usefulness to v0.18.441.

**Rollback:** disable `general_task_engine_enabled` or revert this
release if live tests show target misresolution, unnecessary reads,
provider cost regression, safety/permission mistakes, incomplete
historical answers or routine status/control latency regression.
Do not remove the operational deadline to mask runaway behaviour.
