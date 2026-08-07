# Hubitat MCP AI 0.10.361

## Fixed

- **"Recommend useful automations for my home" (and any other
  `automation-status` answer) never showed the assistant's written
  response -- only the raw apps/rules browser widget.** 0.10.360 taught
  the backend to have the model synthesise genuine, grounded new-automation
  ideas into the `message` field, but the web UI's `showAnswer()` in
  `webui.py` had a hard either/or: for `route === 'automation-status'` it
  rendered `renderAutomationItems(data)` (the filterable Active/Disabled/
  Paused/Broken list) *instead of* `renderMessage(rawMessage)`, unconditionally,
  whenever `automation_items` was a non-empty array -- which it always is
  for this route. So the new creative suggestions were computed correctly
  on every request and were sitting right there in the JSON `message`
  field, but the browser never displayed them; only the old item-count
  browser widget was ever shown. Verified live: a real
  `homebrain_control_devices`-free `automation-status` response contained
  five well-grounded new automation ideas (energy-aware robot vacuum
  scheduling, Life360-triggered welcome lighting, a microwave-door safety
  timer, humidity-triggered air purifier, low-brightness night path
  lighting) in `message`, none of which reached the screen.
- Fixed by always rendering `renderMessage(rawMessage)` first, then, only
  for the `automation-status` route and only when `automation_items` is a
  non-empty array, appending the existing browsable items widget
  afterwards. Both are additive now -- the user sees the assistant's
  written answer (including any new-automation suggestions) followed by
  the full searchable/filterable app and rule list, instead of one or the
  other.

## Context

This is a pure front-end display bug in `hubitat-mcp-ai/rootfs/app/webui.py`
(`showAnswer()`). No backend routing, grounding, or automation-status logic
changed -- 0.10.360's `automation_ideas_service.py` was already producing
the right content, it just never reached the page. Found via a live
side-by-side: the raw JSON response to "recommend useful automations for
my home" contained the expected synthesized ideas, but the rendered page
only showed the item-count accordion.

## Validation

- `python -m pytest -q` -- 590 passed, including 2 new regression tests
  (`test_automation_status_answer_always_shows_message_text_first`,
  `test_automation_status_items_widget_is_appended_after_message_not_instead_of_it`)
  added to `tests/test_webui_automation_sections.py`.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.361.
- `python scripts/analyze_imports.py` -- zero orphan modules.
