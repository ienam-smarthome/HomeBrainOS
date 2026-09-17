# Hubitat MCP AI 0.10.450

- Make deterministic history-duration arithmetic visible in structured evidence. Successful `homebrain_device_history` receipts now expose a bounded temporal proof containing the device label, attribute, requested history window, total active duration/seconds, interval count, longest interval, coverage, and lower-bound status.
- Replace the generic local-tool evidence summary for temporal history with an auditable concise summary such as `intervals=5, total=4h 31m (16260s), longest=2h 38m, coverage=complete`.
- Add a narrow final serialization guard for explicit total-duration claims. When one authoritative history receipt proves a deterministic total and the model emits a contradictory numeric total, `/api/ask` replaces that claim with the deterministic summary instead of exposing the mismatch as grounded fact.
- Mark the copied evidence receipt with `finalAnswerCorrectionApplied: true` when that consistency guard fires, without exposing the rejected model wording.
- Keep the guard deliberately scoped: correct totals pass through unchanged, longest-interval-only answers are not rewritten, multiple history receipts are not collapsed into one answer, and partial-boundary totals retain lower-bound wording.
- Add regression coverage for the Big lamp 4h31m fixture, structured temporal evidence, contradictory 4h29m model output, correct-model pass-through, and longest-only pass-through.
