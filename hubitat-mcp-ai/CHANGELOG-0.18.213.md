# Hubitat MCP AI v0.18.213 — Fast evidence-ready general answers

## 29 October read-only general health replay

v0.18.212 successfully retrieved ten Hubitat source reads and published 51 stale and one unknown-activity devices along with additional state/metrics. But the answer was a long host-verified fact list, the model's last JSON-only claim selection was unusable (`non_structured_answer`), and the model-only final call consumed **8,010 ms** of a **38,475 ms** run. No independent evidence confirmed any stale device physically offline, or that a referencing automation was broken. The two MCP Rule Server errors describe rejected gateway/tool argument shapes and are not equivalent to a physical device fault.

## Changes

- Introduce `native_answer_brief.py`: a universal read-receipt-based source fact briefing, selecting a small bounded set of independently verified claim-catalog observations across available source types. No question wording, specific device ID, app ID, router, inferred fault ranking or unvalidated model narrative is used. Staleness and app-reference limitations remain explicit.
- When model-led READ planning reaches its explicit **round/read budget** with at least two independently returned operations, two claim kinds and three verified facts, prefer the existing verified source facts over an extra **up-to-8-second** model-only JSON claim selection. This does not bypass model planning or tool selection, does not apply to isolated/incomplete source evidence, and leaves the incident-specific source-authoritative pathway intact.
- The user-facing `answer.text` now carries the concise source-grounded briefing when that readiness condition holds. The full verified claims, all original read descriptions and failures stay in `report.text` and diagnostics.
- Emit `general_evidence_readiness` and `concise_answer_source` diagnostics. Their distinct operations/fact kinds counts are **coverage proxies only**, not scores of correctness, Claude parity, or V1 superiority.
- Add cross-domain read-agent regression cases (general health, incident diagnostics, broad hub review), publication ordering, no fabricated absence, model injection resistance, single-source no-shortcut and source-depth diagnostics.

## Evaluation: V2 vs V1

A paired live comparison still requires running **the same objective** through the normal Main Ask V1 and Native READ V2 with unchanged Hubitat state, then checking: (1) answer correctness and relevance, (2) operational/causal reasoning quality, (3) missing or contradicted sources, (4) required evidence coverage, (5) elapsed time and model/Hubitat read time, and (6) unintended write operations. Neither raw test count nor model speed alone establishes superiority.

This release improves general evidence presentation/latency only. It does not complete unrestricted natural-language synthesis or source-verified multi-step causal reasoning. Native V2 remains experimental and read-only.
