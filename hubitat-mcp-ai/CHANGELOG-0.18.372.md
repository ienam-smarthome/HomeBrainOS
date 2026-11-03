# HomeBrainOS v0.18.372 — bounded model-initiated reads and actionable timeout diagnostics

## Real first-attempt Q2 reliability observation (2026-11-03)

The registered `device_mqtt_conflict` read-only question, run in the user's HomeBrainOS app with the free Gemma default, failed after the **180-second investigation deadline** while **Executing tool calls (round 2/6)**. The error response was `success=false`, `route=error`, and reported **no verified read-only results**. The screenshot indicated that MCP and Ollama were nominally online; this is not evidence that the individual tool call succeeded. No agent reasoning answer, actual per-tool failure logs, request ID or independent upstream trace was supplied. **The stalled operation and precise root cause remain unverified**; do not assert it was MQTT, the broker, Hubitat, the model, or the network.

In the existing runtime, the `RequestCoordinator` enforces an overall 180s investigation deadline and includes the request ID in server logs, but the returned 504 message told users to find that ID without presenting it. Separately, model-selected read tool execution could wait on a local helper or MCP queue/transport without its own outer wait budget. This *could* consume the request's whole deadline; it is a testable reliability risk, not a retrospective proof of this particular failure.

## Change

- A model-selected **non-mutating read** is bounded by `asyncio.wait_for(..., 30s)` over its first local-handler/MCP remote operation. MCP's own 25s request timeout remains configured separately. The 180s overall investigation deadline remains the final ceiling; it is **not increased**.
- On model-read timeout, cancel the pending awaitable, emit exactly one **failed read receipt** with `success=false`, `supports_live_claim=false`, and a model-visible explanation that the source was unavailable. Never construct an observed device state or infer historical source absence from a timeout. Count `model_read_timeout` and log only the declared gateway/tool name.
- **Host-originated**/nonmodel reads retain their own existing time policy. **Mutating calls retain their existing confirmation and execution policy and are never subjected to this read timeout.** A timed-out read is not retried automatically by the executor.
- Diagnostic HTTP 504 now includes the existing generated **request ID**, so users can correlate the exact event with the add-on log. No token, device name, raw model prompt or private network address is added to that message.

The bounded wait applies to the awaited handler/MCP operation. It does not prove every later synchronous projection or cleanup path completes within 30 seconds. Nor does it guarantee that a six-round investigation will never use all 180 seconds if multiple independent calls/timeouts exhaust the budget.

## Tests / acceptance

Offline mocked regression tests: a never-returning MCP tool and a never-returning local tool cancel promptly and yield unsuccessful read-only receipts; host read behavior unchanged; a simulated *already-authorized* write is not interrupted by the read ceiling; the 504 contains the same request ID logged by the server. Existing release gate, no-read-data timeout semantics and mutation/confirmation protections must remain green. Never test with a live Hubitat write.

**Before:** One actual Q2 request reached the 180s deadline with zero verified reads. **After live on an installed add-on: NOT MEASURED.** Tests demonstrate per-call cancellation semantics but cannot establish whether the particular user's stalled operation is the same code path. This does not measure causal/MQTT answer quality, model superiority or provider/model latency distributions. For live diagnosis, use the now-visible request ID and add-on logs; do not immediately retry a costly 180-second question without understanding the first failure.

## Rollback / independence

Rollback the bounded read call and request-ID formatting if they interfere with valid read paths; restore v0.18.371 package metadata. No native one-time Rule Machine writer permissions, upstream class source, cloud-model selection, temperature/device control, Home Assistant configuration or historical user data were changed. This reliability fix is independent of the previously observed unverified external-cause answer and of the upstream Rule Machine issue.
