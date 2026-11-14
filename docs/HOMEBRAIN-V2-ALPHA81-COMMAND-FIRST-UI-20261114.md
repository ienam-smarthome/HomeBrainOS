# HomeBrainOS V2 alpha.81 — command-first interface

**14 November 2026. Scope: `hubitat-mcp-ai-v2/` only.** The maintained V1 `hubitat-mcp-ai/` add-on is deliberately unchanged; its v0.18.460 redesign is not moved, reverted, cherry-picked or modified by this branch.

## V2 architecture and UI contract

V2 already has its own self-contained `rootfs/app/ui.html`, FastAPI routes, per-request `Interaction` approvals, `home_overview.py` source-scoped read-only snapshot, source-preserving agent and independent diagnostics/evaluation. Do not import V1's `ConfirmedActionCoordinator`, dashboard APIs, tool-effect registry or app code. Existing `/api/ask`, `/api/activity/{request_id}`, `/api/activity/{request_id}/confirm`, `/api/overview`, `/api/status`, TTS and evaluation endpoints remain authoritative and unchanged.

The new UI prioritizes a sticky microphone/text/Ask bar; Enter submits and Shift+Enter inserts a newline, `/` focuses, Esc clears. Tap starts browser en-GB recognition, second tap sends; holding longer than 400 ms and releasing sends. If recognition is unavailable or blocked, the input remains usable and the privacy warning remains visible. Newest answers appear immediately below the command bar; older ones remain beneath with per-answer copy/review/read-aloud and PRIVATE JSON downloads. Original source receipts are displayed in collapsible drawers, not recomputed. The work trace uses actual selected native tools observed via polling and original `tool_calls[].elapsed_ms` or `answer_stage_trace` stages; there is **no claim of exact phase duration when absent**.

The overview tiles reuse the existing one-shot read-only inventory request and retain its coverage/names/uncertainty notes. The 1,000 px-and-wider layout has a slim sticky right rail; smaller viewports show a compact four-count strip. The status pill expands model, version, MCP setup and the existing read-only monitor connection check. Existing Hub Diagnostics and AI Evaluation tabs, graph popouts and evaluation consent are retained.

## Approval safety

V2 does **not** use V1's confirmation coordinator. The existing native `Interaction` instance owns the request-specific pending action, UUID approval and `/confirm` endpoint. To make UI cards truthful for ordinary device writes, the *web request* constructs its `Interaction(require_native_write_approval=True)`; non-web Interaction defaults remain unchanged. V2's existing `is_native_action_proposal(name,args,catalog)` source-driven predicate is reused with a conservative read check, without user-prompt parsing or client-selected devices/rules. No write is sent to MCP until the UI confirms the exact pending proposal.

The pending preview contains only redacted, bounded structured native tool name, operation verb and device/time/day display fields. It cannot be used for native execution. Effect display buckets are `read`, `routine_write`, `sensitive_write`, `destructive_write`, derived from the selected native entry/leaf and arguments rather than the user's message. Sensitive and destructive cards require an extra browser confirmation; all approval still goes to the same original UUID bound to the current request. Edited chips disable Approve: Edit first declines the queued operation and starts a new model-led question. Dry-run is only a *proposal preview*, explicitly not a native simulation; no Undo exists without a verified inverse contract. If a model call fails after a submitted write, the existing alpha.80 executed-write source evidence is still shown without retries.

## Testing and acceptance

The new fictional Python tests cover direct and mixed native tool approval gating, classification, no approval for reads, declined writes, structured preview and UI contracts. Existing V2 JavaScript fixture tests, standalone browser smoke and full V2 CI are required to remain green. A structural passing result does not prove that a particular live model, browser speech-service permission or actual Hubitat action will behave correctly. After installation, run a read-only Ask/voice/receipt acceptance followed by a **user-authorised** noncritical write if necessary. Never test on live hub during development and never count coached acceptance as a blind Gate B case.

No user-authored standing defaults, paid model routing, V1 UI or V2 model reasoning strategy is changed.
