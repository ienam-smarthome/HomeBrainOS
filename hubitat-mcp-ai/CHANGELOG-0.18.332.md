# v0.18.332 — Q1 telemetry explanation / technical-detail separation

## Evidence prompting this release

One privately reviewed read-only HomeBrain response from `0.18.331` to a registered device-health-vs-MQTT question included a 43.533-second wall time, 13 tool calls, 10 Ollama Cloud Gemma rounds, and a long terminal evidence projection. It correctly treated broker/endpoint reachability as separate proof dimensions but did not clearly answer the connection-status question up front. Source-code offsets, missing source-method proof, and an empty command section were exposed in the natural answer, even though those data were already present under Technical details.

**This is one unscored diagnostic, not an authenticated frozen-prompt baseline, a verified physical root cause, or a controlled same-packet before/after model-quality result.**

## General presentation change

- The generic `device_telemetry` finalisation path keeps retrieved driver code offsets and the missing-discriminator ledger under `investigation_coverage.additionalSourceCodeEvidence` and `incidentReasoningDepth`. It no longer pastes both into the natural-language response by default.
- If cached source timestamps conflict, show that qualification **after** the opening diagnosis rather than as a pre-answer headline. The quantitative clock disagreement and `rootCauseVerified=false` remain unchanged.
- The source-bounded MQTT status summary explicitly frames broker/session versus endpoint contact as **a possible explanation**, never an authenticated driver-code interpretation or a physical-cause verdict.
- Omit empty "Recorded command sources" / "Command outcomes" paragraphs when the bounded event sample contains no commands; retain the counts, history-integrity limitations and acknowledgment status in structured technical evidence.
- No new tool lookups, retries, provider/model rounds, network requests, AI routing changes, state writes, or control API changes.

## Acceptance and limits

- Anonymised cross-device tests assert that a telemetry message leads with diagnosis, no empty command section or source-chunk ledger is leaked into prose, while the source and depth metadata remain available.
- Unsupported physical reachability, code-installation, clock certainty and root-cause claims remain prohibited.
- The model's initial draft is **still subject to** the existing deterministic telemetry projection; this presentation simplification does **not** solve the larger model-led publication architecture problem.
- **Actual before/after answer-quality and latency improvement remain unmeasured.** A controlled same-evidence model replay and independent review are required before claiming improvement.

## Rollback

Revert the presentation-only changes and version update if the response omits critical diagnostic context for an explicitly requested task. No persistent state or API schema migration is required.
