# Hubitat MCP AI 0.16.67

## Direct production-path performance finalization

- Removes the `sitecustomize.py` startup hook added in 0.16.66 after live proof showed that hook was not active in the serving process.
- Wires performance finalization directly into `app.py`'s `_agent_request()` path, which is the actual path used by `/api/ask` and `/api/chat`.
- Adds `performance_api_finalizer.py`: when a returned outcome contains successful `hub_get_performance_stats` evidence, it performs one bounded recent-log read (`hub_get_logs`, `since=30m`, `limit=100`) through the live MCP client if logs are absent.
- Extends the returned outcome evidence with the API-path log receipt, runs evidence-scoped synthesis/repair over the measured statistics plus recent-log observations, and applies `guard_live_performance_semantics` before serialization.
- Adds API-path observability counters for log attempt/success/retry/failure/reuse and records `performance_api_finalize` timing.
- Replaces the 0.16.66 startup-hook regression with production-path tests that exercise `_answer_result()` -> `_agent_request()` -> performance finalizer and verify the exact unsupported 0.16.66 wording is fail-closed.
- Updates the canonical runtime module map to remove `sitecustomize.py` and register `performance_api_finalizer.py`.
