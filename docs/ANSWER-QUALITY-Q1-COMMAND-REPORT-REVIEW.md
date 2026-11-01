# Q1 source-bounded review — command issuer vs reported transition

**Review date:** 2026-11-01. **Programme:** permanent Answer Quality charter, Q1.  
**Privacy:** anonymised findings only; no raw household device, app, time-history, location, credential or event payloads are committed here.  
**Result classification:** **one diagnostic source-reviewed output, not a validated frozen-prompt first-attempt benchmark**.

## Run identification and measurement boundaries

- User-supplied HomeBrain answer and technical JSON: full response available to the reviewer in the private conversation, not committed.
- Reported add-on: `0.18.330`; model: `gemma4:31b`; provider: Ollama Cloud, Free.
- Technical result: `outcome=unresolved`, `rootCauseVerified=false`, `questionResolved=false`, `evidenceComplete=false` while `sourceChecksComplete=true`. Source checks are not causal verification.
- Actual reported wall duration: **25.181 seconds**; agent phase: **22.459 seconds**; provider aggregate: **19.563 seconds**; **8 tool calls**, **6 model rounds**. One recorded synthesis-validation issue, one attempted causal-provenance repair, and one failed repair. One read-only dependency lookup failed. These are diagnostic counts, not an accuracy score.
- The **exact submitted question** was not independently recovered from the response, and **the running add-on's Git SHA** was not authenticated. The response's version number alone cannot confirm its exact deployed code SHA or initial-attempt status.
- **Formal source-graded frozen prompt denominator: 0.** Do not put this trace into `answer_quality_scorecard.py` as a current-`main` result or claim before/after improvement.

## Source review of the answer

A bounded device-command history recorded an OFF command attributed to a named button-handling **app**. An OFF state report was timestamped **129 milliseconds later** and carried bridge **reporter** provenance. A separate bounded source-history view placed the corresponding ON and OFF reports approximately **2.56 seconds** apart. The switch history itself explicitly said its source completeness was **not independently verified**.

| Answer component | Assessment | What can be stated |
| --- | --- | --- |
| Recorded OFF command issuer | **Supported** | App `producedBy` identifies the issuer of the recorded command; it does not independently authenticate the upstream button or physical press |
| OFF state report and 129 ms interval | **Supported** | Source timestamps establish command-before-report temporal order, not command delivery or physical execution |
| Short ON interval | **Supported within returned history** | Approximately 2.56-second reported-state interval; the broader history is bounded and not physically verified |
| Bridge provenance | **Supported as reporter** | Report-producing device is not necessarily the command origin |
| Other apps in `triggered[]` | **Supported as notified listeners only** | Listener metadata alone does not prove initiation or non-initiation through another route |
| Definitive “direct cause” and “execution” framing | **Overconfident** | The strong temporal correlation supports an explanation by a recorded OFF request, but no independent command-to-actuation proof was present |
| Specific upstream physical controller identity | **Correctly left unresolved** | An app label does not uniquely identify the human action or device |
| Resolution certainty | **Inconsistent** | The answer sounds resolved although the same technical packet declares the causal question unresolved |

**Quality judgement (diagnostic, non-scorecard):** useful issuer attribution, accurate recorded ordering and reporter/listener separation; remaining causal-certainty overstatement and unclear separation of recorded command from confirmed execution. Evidence quality is stronger than an answer that blamed the bridge merely because it reported the state. This **does not** establish a same-input before/after improvement, a successful first attempt under the frozen protocol, or a current-main quality percentage.

## Generalisable Q1 follow-through

The privacy-safe capture script initially read `investigation_coverage.missingSourceKinds` only. The response contract's actual missing-source array is nested under `investigation_coverage.sourceCoverage.missingSourceKinds`. An empty nested list must be **reported empty**, not misclassified as **not provided**, while `evidenceComplete=false`, historical integrity warnings and failed synthesis repairs must remain visible **as self-reported metadata**, not a factual-grade verdict.

This metadata-contract correction and anonymised review are offline Q1 work. They do not change production narration, call the model, or modify Hubitat/HA. Any future runtime reasoning adjustment needs cross-domain negative controls and **the same source packet/question before/after**; do not add a phrase- or room-specific post-processor.

**Next:** verify the actual registered input prompt and deployment SHA only if retained in existing read-only diagnostics. Then collect fixed first-attempt reviews with original evidence; do not retroactively certify this run as a frozen benchmark. Until then the official baseline is `not_measured`.
