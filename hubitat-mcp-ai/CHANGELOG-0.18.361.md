# Hubitat MCP AI v0.18.361 — safe provider-round latency diagnostics

## Grounded motivation, not a speed claim
The user-supplied first-shot v0.18.360 Bedroom 1 Light bounded-history investigation was **correct and source-grounded** on all eight in-window switch reports, with `requested_event_window_packet=1`; however it took **25.338 seconds**, of which the request recorded **20.078s provider time**, **five gemma4:31b-cloud model rounds** and five tools. The current `model_round_details` output showed only five repeated `{model, provider}` rows, so it was impossible to distinguish time spent selecting tools versus final model synthesis, or even whether the final round dominated. The prior Fridge and motion/light results differ in source and complexity; no cross-version paired latency change has been established.

## General minimal instrumentation
`request_metrics.record_provider_model` now optionally retains for each successful provider round, using its existing request-local bounded `model_round_details` list:
- `elapsed_ms`: wall duration of one provider round, including local preparation/streaming and the optional single empty-response recovery within that same call; **not** just server inference time.
- `result_kind`: `tool_calls` or `answer`, derived solely from the returned structured tool-call list.
- `tool_call_count`: number of structured tool calls the model requested in the round, regardless of whether the gateway later accepted/executed them.
- `declared_tool_count`: number of tool schemas offered to the provider during that round.

Both Ollama (free/cloud/local) and Claude transport call the existing recorder after success, using monotonic clocks. Old two-argument callers and old `model_round_details` rows remain valid, and failures do not falsely count as completed model rounds. The output is capped at 64 rows and rejects malformed numeric values. It **never retains prompts, model output text, provider reasoning, request URLs, API keys, tool names or arguments, device names, IDs, source logs or private response content**. No changes to tool admission, response text, read-only controls, model-round count, prompts or model provider routing.

## Offline checks
Synthetic test transport with a structured tool-call round followed by an answer round verifies two rows, nonnegative measured durations, tool-call-vs-answer kind, declared-tool counts, no private source leakage and no additional calls. Failed provider attempts are not successful rounds. Backwards-compatible direct recording, invalid metric bounds and per-request context isolation/cap are tested. These are **diagnostic integrity tests**, not a guarantee of latency reduction.

## Next measurement
When v0.18.361 is installed, collect one fresh unrelated read-only status/history first answer with Technical JSON. Distinguish the measured `model_round_details[].elapsed_ms` contributions by `result_kind` and offered tool count. Evaluate **whether** high time occurs in tool choosing, final synthesis or an exceptional recovery. This is not a matched A/B speed improvement until actual source-identical runs are assessed. The explicit-zero history path introduced in v0.18.360 remains **NOT VERIFIED live** and should be tested when a genuinely zero-result source is returned; do not fabricate such a case or repeat a fixed device query.

**Not measured:** production per-round latency distribution, token usage, overall p50/p95, groundedness improvement, Claude parity, provider latency reduction, or user-perceived quality. This release only enables their diagnosis.

No live Hubitat or Home Assistant reads, writes, settings or automation changes were made. Merge only if all exact-head CI checks are green; roll back on leak, incorrect diagnostics or behavior regression.
