# Hubitat MCP AI v0.18.460 — Command-first WebUI

**14 November 2026 — UI, structured approval presentation and safety.** This is a change for the maintained `hubitat-mcp-ai/` add-on, not the separate clean-start `hubitat-mcp-ai-v2/` preview. Design reference: the privately supplied `HomeBrainOS · command-first prototype.html` (static mock). Its scripted tool results, invented duration figures and device-specific sample logic are **not** used.

## What changed

- Redesigned the existing self-contained `webui.py` for sticky Ask + mic, Enter/Shift+Enter/`/`/Escape shortcuts, voice hold (>400 ms) and tap toggle, en-GB SpeechRecognition, clear unsupported-browser feedback, and the existing browser-speech privacy notice.
- Moved real answer cards into a newest-first exchange feed, retained in-page follow-up context, per-answer Copy answer / Copy for review / Read aloud, and collapsed receipt/evidence drawers with explicit PRIVATE JSON warnings. No fake or persistent chat history.
- Live work stages come from existing `/api/request-progress` polling; any later model/tool timing rows come only from returned metrics and original evidence receipts. A missing timing remains absent rather than invented. The API does not currently stream every stage transition or retain exact per-stage durations; the UI labels polling timestamps as observations, not measured phase duration.
- Overview tiles use the existing read-only `/api/dashboard` counts for lights, motion, low battery and inspected devices. On wide screens the overview becomes a slim sticky right rail. A status popover uses `/api/status` and exposes Check connection; health, diagnostics and historical journal remain available under a disclosure.
- `action_card_projection.py` presents only allowlisted, redacted structured fields from **already queued** native actions, classified using `ToolEffect` and existing structured call classification; no prompt-to-card inference. Routine writes now join sensitive and destructive operations in the existing `ConfirmationPolicy` queue, so they no longer run before approval in the model-selected native tool path. The existing `ConfirmedActionCoordinator` consumes and revalidates approved immutable actions. Sensitive/destructive cards add a browser confirmation dialog. No orchestrator, model routing, grounding or native write execution change.
- Edit cancels the pending action via a local-only `/api/confirmation/dismiss` route and prepares a NEW user question. Approve never sends edited chips as native arguments. Dry-run displays the immutable proposal only, explicitly without simulation. No fabricated safety or activity history, and no Undo unless a real undo contract is later established.
- Light and dark token palettes, visible keyboard focus, reduced-motion support and 360–390 px layout. No runtime JS dependencies or external assets.

## Integrity boundaries

No local HTML, CSS or voice interaction runs a native Hubitat command on its own. A write is never confirmed by its prose; the server's session-bound confirmation store and coordinator remain authoritative. The policy is configurable; if confirmation is administratively disabled, browser controls cannot impose an independent backend gate. Do not disable confirmations when requiring approval of routine writes.

The UI cannot claim exact model round timing when metrics are missing, nor assert every transient stage observed through polling. The private Technical JSON still contains the original source. A read-only refusal is shown like any other answer; no Approve or Dry-run control appears without a structured pending write.

## Tests and deployment

- Fictional tests cover effect→card projection, nested structured fields, secret filtering, reading-only refusal, routine/sensitive/destructive confirmation, observed stage/receipt rendering, voice and keyboard contracts and inline JavaScript syntax.
- Release gate: `python scripts/run_release_gate.py`. See the PR's exact-head CI for results and fixture screenshots. A green structural gate does not prove household speech microphone permissions, the specific browser SpeechRecognition implementation or live Hubitat behaviour.
- No live Home Assistant, Hubitat, router, or cloud-model calls were made during development. No paid model settings changed.
