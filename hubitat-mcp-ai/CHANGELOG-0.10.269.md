# Hubitat MCP AI 0.10.269

- Extracted pending sensitive-action state into a focused
  `ConfirmationStore`.
- Added same-session one-time consumption, TTL cleanup, replacement-question
  cancellation, and a 128-session capacity limit.
- Rejected empty session identifiers before sensitive actions can be queued.
- Deep-copied queued actions and messages so later model or request mutation
  cannot alter an awaiting confirmation.
- Kept tool-effect classification, action limits, confirmation prompts, and
  confirmed execution in `UnifiedMCPAgent`.
- Added direct lifecycle, expiry, isolation, and capacity regression tests while
  preserving the existing end-to-end confirmation suite.
