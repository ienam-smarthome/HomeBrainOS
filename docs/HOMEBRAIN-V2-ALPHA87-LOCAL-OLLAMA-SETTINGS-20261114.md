# HomeBrainOS V2 alpha.87 — local Ollama throughput settings and optional Supervisor keys

**14 November 2026. V2 Preview only.** No V1, device-control, MCP, approval or cloud-failover behavior changes.

## User-supplied local inference evidence

The owner's Qwen 3.5 4B local Ollama server responded correctly to a minimal `/api/chat` request using `think:false`, `options.num_ctx:8192`, and `stream:false`. Reported timing was 8.76 seconds total, including 8.34 seconds of model loading, 15 prompt tokens and 2 completion tokens; `ollama ps` showed 100% GPU execution and an allocated 8K context (roughly 3.4 GB). This proves **one short API response**, not a HomeBrain full-tool prompt performance benchmark.

A separate installed V2 alpha.86 local Qwen request hit a 120-second model round timeout before any model reply or MCP call. The root cause is **unverified**: the fully configured Hubitat skill and tool catalogue are substantially larger than the short local test, and previous local model thinking was enabled by default. Do not attribute the timeout definitely to either without source-real measurement.

## Implementation

- New V2 `local_ollama_think` (default `false`) and `local_ollama_num_ctx` (default `8192`; configurable 4096–32768) options. They are sent to **private-LAN/local Ollama primary URLs only**, as native `POST /api/chat` JSON fields `think` and `options.num_ctx`.
- Retain the *same* native MCP catalogue, model-selected tools and confirmation contract. No prompt compression, new planning heuristics, forced data reads, Ollama Cloud request change or automatic cloud fallback on inference timeout. Fallback remains first-connect-failure-only.
- Record only original numeric Ollama `total/load/prompt evaluation/generation` timings (milliseconds) and token counts per completed model round in the PRIVATE `model_round_metrics` answer. A timeout without a completed response still has **no Ollama timing counters** and no evidence of model output. Failed initial local attempts are explicitly tagged `model_route.attempted_provider=local`; `provider=null` continues to mean no completed model round.
- The V2 status exposes whether local tuning is active and the selected context/thinking settings. It performs no inference or active connection probe.

**Trade-offs:** Disabling thinking may improve latency but reduce complex first-answer quality. Increasing context consumes VRAM; 8K is a tested starting point, **not** proof it is sufficient for HomeBrain's entire MCP tool schema. Increase to 16K cautiously if source-real tests show truncated context or tool discovery failures while GPU execution remains acceptable. Performance counters are sourced solely from completed native Ollama responses and may be absent from older endpoints.

## Supervisor configuration-save correction

Home Assistant's Supervisor may regard keys present in add-on `options:` as required even when the matching schema uses optional `password?` or `str?`. The previous alpha.86 packaged optional empty-string credentials (including `model_api_key` and `cloud_fallback_api_key`) in `options:`, producing a save error in the add-on configuration editor.

Alpha.87 removes **blank optional keys from the packaged `options:` defaults**, but leaves their optional schema entries intact. The runtime `app.py DEFAULTS` still supplies empty strings when omitted; existing saved non-empty credentials and options are not cleared by the runtime loader. Operators may explicitly add optional keys in the add-on's YAML configuration editor.

## Recommended local configuration

```yaml
model_base_url: "http://YOUR_WINDOWS_PC_LAN_IP:11434"
model_name: "qwen3.5:4b"
local_ollama_think: false
local_ollama_num_ctx: 8192
model_timeout_seconds: 120
cloud_fallback_enabled: false
```

Set `cloud_fallback_enabled: true` **only with deliberate consent to send private question/MCP evidence to an external provider** and a private OpenRouter free API key; an exhausted Ollama Cloud key is not required for the local primary. `model_api_key` should be omitted or left empty. Verify LAN connectivity separately; `localhost` in Home Assistant is not the Windows PC.

## Tests and acceptance

- Fictional mocks assert local `think:false`, `options.num_ctx:8192`, complete unchanged messages and tools, source-numeric performance metrics, configurable thinking/16K context, hosted-cloud omission of local-only fields, and no cloud failover on generation timeout.
- Add-on schema regression asserts optional blank password/URL options are omitted from packaged defaults but remain schema-valid; actual HA Supervisor editor validation requires installed testing.
- Only deploy to V2 Preview after green CI. With the PC running, use one **fresh READ-ONLY** Ask question, inspect `model_route`, `model_round_metrics`, original tool receipts, and response time. Check `ollama ps` for active 8192 context and GPU residency; if home-tool prompts still time out, capture private status and logs without enabling writes. Compare eventual local first-answer accuracy against the standing Gate B; no success claim until the installed model proves it.
