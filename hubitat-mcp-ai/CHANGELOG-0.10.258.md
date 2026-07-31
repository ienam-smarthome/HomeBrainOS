# Hubitat MCP AI 0.10.258

- Add structured `automation_counts` and `attention_count` fields to automation-status responses.
- Add a clean `display_name` alongside the original automation name.
- Present broken, paused, and unknown items before disabled and active items in the text fallback.
- Include an explicit “need attention” count in the summary.
- Add regression tests for counts, marker cleanup, and problem-first ordering.
