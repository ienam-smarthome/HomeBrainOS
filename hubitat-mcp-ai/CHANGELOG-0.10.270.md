# Hubitat MCP AI 0.10.270

- Extracted request-scoped evidence receipt construction into a focused
  `EvidenceRecorder`.
- Moved nested argument redaction, timestamps, structured effect metadata,
  receipt snapshots, and successful live-evidence detection out of the
  orchestrator.
- Returned deep-copied receipt snapshots so API consumers cannot mutate the
  authoritative request context.
- Kept evidence authority, retry, refusal, and `supports_live_claim` decisions
  in `UnifiedMCPAgent`.
- Preserved temporary compatibility shims for existing internal test and
  integration surfaces while routing production calls through the recorder.
- Added direct regression coverage for context isolation, redaction, immutable
  snapshots, live-evidence qualification, and inferred effect metadata.
