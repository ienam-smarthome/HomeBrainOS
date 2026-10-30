# v0.18.250 — General source-role provenance in the original MCP agent

## Investigation architecture

- Integrates a typed source-role observation packet into the original model-directed investigation checkpoint, using successful read-only device-history receipts instead of keywords or device name rules.
- Preserves the distinction between a state-reporting bridge/device, downstream event subscribers, and a separately source-verified initiating command.
- Surfaces unanswered initiating-command and dependency/execution questions to the model as candidate follow-up reads, rather than granting tools or invoking a hardcoded device-specific workflow.
- Injects the same bounded source-role packet before the original final no-more-tools model synthesis.
- Extends the existing final causal-claim validator to multi-device histories: physical-type/bridge-origin state reports alone cannot justify claiming external/manual initiation, or globally excluding Hubitat commands.
- Source observations include any reported device-state attribute (such as switch, heating or connectivity), not only Bathroom lights.
- Adds request-local unit regression coverage for multi-device overconfidence, genuinely unresolved source roles, command-history exclusions, unrelated answers and invalid receipts.

## Safety and scope

No new permissions, writes, device changes, credentials or externally inferred command issuers. Source-backed causal certainty remains conditional on exact matching execution/command evidence. The agent still needs a richer model-directed dependency traversal and iterative completion mechanism; this release establishes shared evidence obligations, not a complete causal solver.

**Release condition:** Merge only when all required GitHub Actions checks have completed successfully. Live Home Assistant evaluation is separate from repository CI.
