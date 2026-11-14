# HomeBrainOS V2 alpha.86 — local Ollama first, optional free cloud when PC is off

**14 November 2026. V2 Preview only.** Preserve V1, all existing native Hubitat MCP permissions, approvals, model-led tool choice, original receipts and review stages.

## Purpose and scope

Ollama Cloud usage credits are not assumed to be available. The owner's Windows PC runs a local Ollama instance (existing model choices include a Qwen 4B). HomeBrainOS V2 runs as a separate Home Assistant add-on and should query this PC **over its LAN**, with **no Ollama Cloud key**. When the PC is powered off or unreachable, the operator may *explicitly* enable a backup OpenRouter free-model route. **No cloud fallback is enabled on upgrade**; legacy single-model settings remain valid until deliberately changed.

OpenRouter documentation (verified 14 November 2026) advertises `openrouter/free` and IDs ending `:free` at zero model pricing, with a free-tier limit of about 50 requests/day; a multi-round MCP investigation uses multiple requests, and model selection/availability may change. This is a community free service, not guaranteed throughput, quality, availability or future pricing. Validate tool calling on the chosen free model before trusting control operations.

## Configure the add-on

| V2 add-on option | Recommended value |
|---|---|
| `model_base_url` | `http://YOUR_WINDOWS_PC_LAN_IP:11434` (LAN-reachable; **not** `localhost` inside the Home Assistant add-on) |
| `model_name` | `qwen3.5:4b` only if already installed and confirmed to support usable native function calls; choose another actually installed tool-calling model if needed |
| `model_api_key` | empty for ordinary local Ollama |
| `cloud_fallback_enabled` | `false` until the owner explicitly enables cloud transmission |
| `cloud_fallback_model` | `openrouter/free` or a consciously selected OpenRouter `:free` model |
| `cloud_fallback_api_key` | a private OpenRouter API key, stored as a password option; never paste into chat, UI or GitHub |
| `model_timeout_seconds` | keep existing setting (default 120); connection failure detection is separately bounded |

On Windows, allow Ollama to listen on a reachable LAN interface, restrict its TCP 11434 firewall scope to the trusted private network / Home Assistant host, and restart Ollama if environment variables change. Do not expose an unauthenticated local Ollama server to the public Internet. Check `http://PC-LAN-IP:11434/api/tags` from a trusted LAN device before enabling fallback, and verify that the intended local model is pulled.

## How failover works

1. Primary model calls use the existing Ollama `/api/chat` protocol and original native MCP tool schema/receipts. The add-on status has configuration, not an active connectivity claim.
2. Only **connection refusal, DNS/routing failure or a connection-establishment timeout on the first model round** can activate the optional OpenRouter free backup. A slow but connected local model, ambiguous read/generation timeout, HTTP 400/401/402/429/5xx, invalid model response or local missing-model error does **not** trigger fallback.
3. The first successful model response **pins the same model provider for the complete Ask request**, including tool reads, user-authorised writes and final evidence review. Mid-request local disconnection is an error; it is never retried via a different model. A new Ask request may try the local PC again.
4. The OpenRouter connector sends only HTTPS OpenAI-compatible chat-completion requests to the fixed OpenRouter API endpoint and only accepts `openrouter/free` or explicit `:free` IDs. It maps Ollama-style assistant tool calls and original tool results to strictly paired OpenAI `tool_call_id` messages. It does not select or execute any Hubitat operation itself.
5. Status and private Ask Technical JSON identify whether an individual request used local or cloud fallback. They never expose API keys or URLs. The existing confirmation requirement still gates all V2 UI writes.

**Privacy:** Cloud fallback sends the current question, system skill/instructions, selected native MCP tool outputs and other in-request context to OpenRouter and its free-model provider. A free model may be less reliable than the previous Ollama Cloud model. Enable backup only if that external data processing is acceptable; otherwise leave it off and receive a clear local-connection error while the PC is off.

**Cost:** No paid model IDs accepted by the fallback router. No proactive cloud checks, recurring health probes, new MCP reads or scheduler. The fallback itself uses model calls and external tokens, subject to provider rules, rate limits and future changes. No guarantee of permanent free access.

## Fictional regression / installed acceptance

Synthetic tests cover free-model ID restrictions, no key in request payload/status, primary-connect-only failover, provider stickiness after a model reply, independence of successive Ask requests, explicit rejection of missing/unpaired OpenAI tool-call IDs, preservation of user/tool source text, no fallback on ordinary timeouts and HTTP errors, and cloud model response/argument compatibility. They do not call Ollama, the cloud API, Home Assistant or Hubitat.

Install V2 Preview alpha.86 only after CI is green. On **PC ON**, ask a fresh read-only question and verify `model_route.provider=local`, normal MCP evidence, readable UI and reasonable latency. On **PC OFF** (only if desired), explicitly enable the free-cloud backup and ask a *new read-only* question; verify `provider=cloud`, `reason=local_connect_failed`, tool receipts and context privacy. Then bring PC ON and verify a new question returns to local. When testing OFF, avoid command writes and preserve first-answer evidence; do not send production secrets to public issues. Confirm that 429/timeout/invalid credential errors do not silently trigger a paid provider. Do not call installed success from CI.

Standing Gate B source-real accuracy evaluation is still required for local 4B and free cloud separately. They will have different reasoning quality, tool compatibility and latency. **V1 and independent monitoring remain unchanged.**
