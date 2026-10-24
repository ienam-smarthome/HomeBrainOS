# HomeBrainOS 0.18.88 — Primary objective wins over overlapping rules and secondary synthesizers

## Evidence from 0.18.87 live read-only test

A named Groovy investigation asked why Device Status Report app **3977** raises `LimitExceededException` at `setReportData` line 64, with device Display **7182**. HomeBrain successfully resolved installed app instance **3977** to Groovy source code **1410** and fetched **81,240 of 81,240 characters in two continuous pages**. It then delivered a canned **existing Rule Machine verification** message (stopped=false, no local variables, unknown IF/action tree), rather than diagnosing the requested method. The source-completion guard mistakenly set `questionResolved=true`, `analysisAnswerVerified=true`, and `objectiveSatisfied=true` even though its own `methodBodyCoverage` was unverified. Ten Gemma agent rounds plus one extra performance synthesis round yielded an irrelevant response.

## Root architectural collision and changes

- **One dominant investigation intent.** Explicit installed-app Groovy/source intent suppresses the Rule Machine existing-rule and deep-rule classifiers, their premature prefetch and their final answer replacement. A source code ID is still resolved from live installed app metadata, not guessed.
- **No secondary answer hijack.** Once the Groovy source agent has synthesized an answer, the general performance API finalizer no longer invokes a second performance synthesis pass merely because the source investigation also inspected performance measurements. Other performance requests retain their established path. Source evidence review, historical command-claim enforcement, API output calibration and read-only permissions remain active.
- **Completion is about the user's goal.** A small, transparent `source_answer_focus` check ensures an explicitly named method (and error class, if requested) is actually addressed in the final answer. If not, report `analysisStatus=source-answer-off-objective`, `questionResolved=false`, `analysisAnswerVerified=false`, `objectiveSatisfied=false` even when complete source retrieval succeeded. Do not misrepresent this lexical focus check as proof of correct code reasoning or causality.
- Regression tests replay the exact source/rule intent overlap, full-source/off-topic final answer, and performance-fallback interception.

## Limitations and future architecture direction

This release is a focused boundary correction—not a complete multi-agent rewrite and not proof of independent Claude-quality root-cause reasoning. A broader design should limit deterministic code to safe tool permissions, identity, scopes, evidence storage and completion gates while retaining a single model-led plan → MCP tool call → result → hypothesis/recheck → answer loop. Future tests should verify method-body evidence and trace caller/scheduler behavior, not just file bytes or model output phrasing.

No Hubitat rule, device, application, configuration or paid-routing state has been changed. The App 3977 excessive-load root cause remains unverified without method-level source-and-runtime correlation.
