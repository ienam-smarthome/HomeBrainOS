# Hubitat MCP AI 0.16.66

## Production performance finalization

- Ordinary `live-read` completions that contain successful `hub_get_performance_stats` evidence now enter the shared `FinalAnswerCoordinator` before the request evidence scope closes.
- This activates the 0.16.65 host-enforced bounded recent-log read (`since=30m`, `limit=100`), current-turn evidence ledger, performance semantic validation, and repair path on the production route that previously returned provider prose directly.
- The routing shim is isolated in `sitecustomize.py` and is evidence-driven; turns without successful performance-stat evidence are unchanged.
- A request-local `ContextVar` records whether `_final_answer()` already ran, preventing duplicate synthesis while still validating performance turns where the provider fetched logs itself.
- The API serialization boundary applies `guard_live_performance_semantics` as a final fail-closed backstop.
- Exact regression coverage reproduces the 0.16.65 no-log bypass and rejects the unsupported live phrases around qualitative database size, imminent backup/data-loss severity, assertive LG implementation hypotheses, scheduler-to-CPU attribution, and unverified `sessionTick` interval tuning.
- `sitecustomize.py` is registered in the canonical runtime module map.
