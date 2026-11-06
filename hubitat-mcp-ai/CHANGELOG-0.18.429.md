# HomeBrainOS 0.18.429 — streamline HomeBrain dashboard and retire scheduled one-time rule cleanup

- Remove six redundant quick-action shortcuts (including the hardcoded Hubitat backup URL and MCP refresh button) and their dedicated event handlers/styles.
- Remove the Advanced testing & diagnostics panel, Legacy Cloud experiments, and Live Shadow experimental UI, including their browser-side JavaScript and unused CSS. Keep the independent read-only developer API endpoints and pure test modules for current Answer Quality workflows.
- Remove the One-time rule cleanup UI, status/run APIs, automatic scheduler, mutable cleanup service, options and tests. No cleanup is invoked by HomeBrain after this update. Existing persisted historical cleanup state, if any, is not modified.
- Keep regular System Check, Hub Diagnostics (including 30-day history and verified startup markers), Historical Journal, Ask/Speak, dashboard tiles, and normal Rule Machine read/write integrations untouched.
- Remove only the unused refresh route linked to the deleted shortcut; normal MCP startup, status, and agent execution are unchanged.

**Upgrade:** Update Hubitat MCP AI from v0.18.428 to v0.18.429 and restart the add-on; do not reboot Hubitat. No rules or devices are altered. Home Assistant add-on configuration automatically drops retired cleanup options when new schema is applied.
