# HomeBrainOS Entity and Execution Core

This document defines the migration path from route-specific device matching to one shared, typed resolution and execution contract.

## Goals

- Resolve a device name consistently across fast routes, the AI planner, MCP tools, and follow-up commands.
- Prevent sensors and read-only devices from being selected for unsupported mutations.
- Represent ambiguity and missing capability explicitly instead of guessing or returning a generic failure.
- Preserve deterministic fast controls while allowing the AI planner to handle contextual language.
- Make tool execution and verification evidence machine-readable before natural-language synthesis.

## Phase 1: central resolution contracts

`entity_resolution.py` introduces:

- `ResolutionRequest`
- `ResolvedTarget`
- `ResolutionResult`
- `ResolutionStatus`
- `resolve_devices()`

Resolution statuses are:

- `resolved`
- `resolved_group`
- `ambiguous`
- `not_found`
- `unsupported_action`

The resolver scores candidates using exact and normalised labels, room assignment, device type, ordinal numbers, fuzzy similarity, and action capability. Every candidate records its match reasons for diagnostics.

## Phase 2: adapter integration

Route all existing device lookup entry points through the central resolver:

1. Exact fast controls
2. Contextual controls
3. `homebrain_search_devices`
4. Planner recovery after a broad inventory call
5. Dashboard device-control endpoints

Existing routes should translate their input into a `ResolutionRequest` and consume only `ResolutionResult`. Route-specific fuzzy matching should then be removed.

## Phase 3: typed execution evidence

Add an execution envelope with separate fields for:

- request parsed
- targets resolved
- command submitted
- hub accepted
- state observed
- verification completed
- warning or error reason

The user-facing result should distinguish:

- **Completed** — accepted and verified
- **Sent** — accepted but not yet observed
- **Failed** — rejected or execution error
- **Uncertain** — insufficient evidence to make a reliable claim

## Phase 4: structured conversation state

Store short-lived state separately from raw chat history:

- last resolved device IDs
- last room
- last intent and action
- last requested period
- pending confirmation
- pending ambiguity candidates
- expiry timestamp

This supports natural follow-ups such as “turn the second one off”, “do the same in bedroom 2”, and “what about yesterday” without sending unrelated history to the planner.

## Compatibility rule

During migration, existing routes remain authoritative for execution. The resolver is introduced behind adapters and tests first. A route must not change mutation behaviour until its current scenarios and failure modes are represented in regression tests.
