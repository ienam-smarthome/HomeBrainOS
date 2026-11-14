# HomeBrainOS V2 alpha.89 — cloud-only inference and explicit model testing

**14 November 2026. V2 Preview only.** Remove **local Ollama from the active HomeBrain V2 inference path**, keep V1, native Hubitat MCP, external health recorder, device monitor, security and write approvals unchanged.

## Why cloud-only now

Two PRIVATE installed local `qwen3.5:4b` V2 first-answer evaluations on different current-device questions produced 0 successful MCP tools and 0/6 applicable first-answer quality. One took about 34.4s, the other 27.4s, with ~4,098 prompt tokens per answer, while the installed model used GPU and thinking was disabled. Earlier alpha.86 also timed out before a first model round. These are **two failures on one local model**, not proof all smaller/local models fail, nor proof all cloud models succeed. Owner elected to remove the local LLM path and prioritise cloud testing.

## Config (Home Assistant add-on)

Alpha.89 uses a **fixed HTTPS OpenRouter API endpoint** with OpenAI-compatible chat completions and original native MCP tool-call pairing.

| Option | Default | Use |
|---|---|---|
| `cloud_mode` | `free` | Either `free` or `paid`, no automatic mode switching |
| `cloud_free_model` | `openrouter/free` | Or an explicitly named OpenRouter model ending `:free`; non-free IDs rejected |
| `cloud_paid_model` | `google/gemini-3.1-flash-lite` | Only used if **both** paid mode and consent enabled; requires a named model, not auto router |
| `cloud_paid_consent` | `false` | Must be `true` with `cloud_mode=paid`; default rejects paid inference |
| `cloud_api_key` | _not provisioned_ | Set a private OpenRouter key via the add-on configuration editor; schema `password?` |
| `model_timeout_seconds` | 120 | Existing model round timeout |
| `investigation_timeout_seconds` | 300 | Existing overall native investigation deadline |

**Example FREE mode:**
```yaml
cloud_mode: free
cloud_free_model: openrouter/free
cloud_paid_model: google/gemini-3.1-flash-lite
cloud_paid_consent: false
cloud_api_key: "YOUR_PRIVATE_OPENROUTER_KEY"
```

**Example manually enabled PAID mode:** `cloud_mode: paid`, `cloud_paid_consent: true`, and a consciously chosen `cloud_paid_model` **after pre-funding/capping the API key**. Do not commit API keys to GitHub or share them in ChatGPT.

On upgrade, old saved `model_base_url`, `model_name`, `model_api_key`, `local_ollama_think`, `local_ollama_num_ctx` and `cloud_fallback_*` are **ignored by V2**; they are not used as OpenRouter credentials. The user must supply the new `cloud_api_key` explicitly. V2 does **not** uninstall Windows Ollama, modify its LAN port, or change V1. Without a configured OpenRouter key, model calls fail closed with a setup message; independent read-only inventory health may still work.

## Routing, privacy, billing contract

- **Free mode:** Accept only `openrouter/free` or models with `:free` suffix. Never send a paid model ID; 401/402/429/errors do not trigger paid fallback. `openrouter/free` selects a suitable free model per request and may change model across rounds. Store provider-returned model and token/cost counters where provided; do not claim a fixed model was used without provider evidence.
- **Paid mode:** Explicitly selected fixed model; requires `cloud_paid_consent:true`. No scheduled spending, automatic free-to-paid promotion, repeated retries, background monitoring, or local-model fallback. **The app does not enforce a monetary spending ceiling**; protect usage using OpenRouter account/key credit limits and pre-funded balance. Charges can still occur for each multi-round task until stopped.
- **Privacy:** In either cloud mode, questions, system skill, tool definitions, original MCP device/event and optional monitor receipts are transmitted to OpenRouter and the model provider. External retention/training rules vary by provider; review provider terms before enabling sensitive features. System Health inventory and diagnostics do not invoke the model.
- **Native controls:** Existing explicit approval before native writes and all Hubitat MCP source-accuracy safeguards still apply. Do not claim a model returning text validates device state, attribution or physical outcomes.
- **Cloud usage data:** PRIVATE Technical JSON now records provider-supplied `prompt_tokens`, `completion_tokens`, `total_tokens`, `provider_reported_model` and only the reported `cost` when returned, alongside existing model rounds and original receipts. No fabricated token or spend data.

## Explicit cloud test workflow (no live Hubitat required)

Open V2 **AI Evaluation → Cloud tool-calling test** and click **Test cloud tool calling**. This makes exactly **one user-initiated cloud model round** with a fictional read-only `fixture_read_state(fixture_id=DEMO_SWITCH)` function. The client observes whether the model emits a correctly formed tool call. It **does not execute the function**, read Hubitat, change devices or send private home data. This consumes one free request or may incur a paid charge if paid mode is deliberately configured. If the free router cannot provide a capable tool-calling model (no valid tool call or HTTP 429), try a consciously selected `:free` model rather than automatically escalating to paid. A synthetic probe pass does **not** demonstrate reliable multi-round real MCP reasoning.

Once the synthetic test succeeds, perform **new read-only** native Hubitat requests and retain original PRIVATE Technical JSON. Evaluate both model-selected tool calls and actual factual answer, source freshness, errors, reporter vs initiator and elapsed time. For difficult causal cases, continue the original Gate B >=12 new first-answer cases across >=6 domains; no live native write should be used as a connectivity test.

## Verified public service reference (14 November 2026)

- [OpenRouter free models](https://openrouter.ai/collections/free-models): all `:free` model variants are zero model price. 50 free requests/day on non-funded accounts, potentially increasing with account credit purchases; failed requests count. Multi-round investigations can exhaust these quickly. The router `openrouter/free` filters on tool support but does **not** guarantee answer quality or a fixed model.
- [OpenRouter Gemini 3.1 Flash Lite](https://openrouter.ai/google/gemini-3.1-flash-lite): published `google/gemini-3.1-flash-lite` at approximately **$0.25/M input + $1.50/M output tokens** and supports tool calling. Changing provider/model, extra usage, hidden/reasoning tokens or platform fees can alter costs.
- [OpenRouter pricing](https://openrouter.ai/pricing): standard pay-as-you-go pricing includes platform fees; consult the current invoice and per-key credit limit to control exposure.

**Never describe GitHub CI, a synthetic cloud model response, or a provider marketing model page as a measured installed HomeBrain first-answer pass.**
