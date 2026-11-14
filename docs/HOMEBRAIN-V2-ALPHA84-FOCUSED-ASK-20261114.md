# HomeBrainOS V2 alpha.84 — focused Ask/Chat layout

**14 November 2026 — V2 only.** The user requested removal of the Home Overview from Ask / Chat and an improved, more legible daily conversation interface. This is a presentation and placement change, not a source, model or device change.

## User experience

- Remove the Home Overview side rail from the Ask section. Use one centred, wider conversation column on desktop and phone, without an empty grid row previously reserved by the rail.
- Make the Ask HomeBrain heading and Latest answer heading visible. Give the input a clearer hierarchy and improve the empty state, answer text spacing, line height and older-message contrast; keep the full model answer, original receipt drawers, Copy for review, private Technical JSON, voice and genuine pending-write approval cards.
- Preserve the existing nine named overview metrics and manual Refresh overview button, but relocate the whole panel into a **collapsed Device overview disclosure inside System Health**. The main System Health Needs attention / Currently reported cards remain directly visible. A collapsed disclosure never hides these health cards or the troubleshooting shortcuts.

## Source and credit boundary

The same **one initial** `/api/overview` request runs as before. Refresh inventory remains explicit and invokes the same single read-only `hub_list_devices` leaf or advertised gateway, plus existing catalog discovery. Opening tabs, expanding the Device overview disclosure, expanding individual names and preparing troubleshooting prompts are DOM-only. They perform **zero extra MCP reads and zero Ollama/model calls**. Pressing Ask retains its existing model-dependent cost and native approval contracts. The recorder status is sourced only from existing `/api/status` data.

No scheduled polling, prompts in source classification, device commands, retrospective status fabrication, new model routing, new runtime dependency, change to Hub Diagnostics/AI Evaluation graphs or change to V1 `hubitat-mcp-ai/`.

## Quality checks

- `tests/test_command_first_ui.py` and `tests/test_ui.mjs` assert the overview markup is absent from Ask and present in System Health, while read-only counts and existing model submission remain intact.
- `tests/browser_smoke.py` checks in fictional desktop/390px Chromium that Ask has no visible overview, that the inventory is initially collapsed under System Health, that names expand there and only manual refresh adds an inventory request. Browser functional, voice, answer/receipts, security and diagnostics paths remain in the existing smoke tests.
- The screenshot workflow supplies disconnected visual fixtures; passing CI does not establish source-real installed usability or actual mobile microphone operation.

## Installed follow-up

Update **Hubitat MCP AI v2 (Preview)** to alpha.84. On both light and dark desktop/mobile, inspect Ask's composer and newest answer, verify no overview rail, then open System Health and expand Device overview for the nine named counts and an optional manual refresh. Check original model/confirmation behavior only with a specifically authorised harmless request; do not issue a live native write merely for a UI check. Resume the existing 12 fresh read-only Gate B first-answer evaluations independently. **V1 remains unchanged.**
