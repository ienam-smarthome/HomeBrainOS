# HomeBrainOS 0.18.20 — Source analysis completion

A live read-only driver investigation retrieved complete Groovy code and device event/log evidence but ended with a generic model action error and was incorrectly marked successful.

This release distinguishes verified source retrieval from a completed code analysis. A bounded source-led workflow moves to final synthesis after a complete contiguous source read, device configuration, scoped history and logs are available. It avoids unnecessary extra source reads.

The final-answer phase receives explicit instructions to explain observed implementation and evidence without requesting tools. If synthesis still fails, the report preserves verified retrieval facts, clearly states the analysis was not completed, and marks the request unresolved rather than successful.

Regression tests cover complete, incomplete, gapped and failed source reads, final-answer failures, unchanged normal responses, and read-only enforcement.

Full GitHub CI and subsequent live Home Assistant validation are required.