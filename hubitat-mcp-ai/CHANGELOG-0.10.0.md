# 0.10.0

- Add safe agent-execution summaries to technical request diagnostics, including tool
  success and evidence counts without exposing full device payloads.
- Surface targeted-search inventory counts, fallback strategy and correction flags so
  live failures can be distinguished from model wording errors.
- Validate manifest/runtime/previous-release metadata and require matching changelogs.
- Make pull-request validation reject Hubitat MCP AI runtime changes that do not bump
  the Home Assistant add-on version.
- Distinguish same-name Hubitat devices by stable ID and remember the user's first
  explicit selection so the same spoken control target resolves automatically later.
