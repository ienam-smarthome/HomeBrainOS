# HomeBrainOS V2 alpha.90 — selectable Ollama Cloud paid provider (14 November 2026)

## Goal and boundary

V2 remains **cloud-only**. Keep the existing **OpenRouter free default** and optional paid OpenRouter model, then add **Ollama Cloud pay-as-you-go** as a separate **manual paid selection**. No local PC dependence, local Ollama connection, automatic free-to-paid escalation, arbitrary URL, fallback, unbounded retries, model benchmarking write, device action, change to V1 or bypass of the native MCP approval contract.

The owner asked to test Ollama Cloud because GPU-hosted local Qwen 4B took roughly 27–34 seconds per one model round and failed to select any native read-only tools in two real first-answer questions. These observations are specific to that model and workflow, not independent evidence of any paid cloud quality.

## Confirmed Ollama Cloud API

Ollama's current docs describe direct HTTPS chat:
```
POST https://ollama.com/api/chat
Authorization: Bearer <private Ollama API key>
Content-Type: application/json
{"model":"nemotron-3-super","messages":[...],"tools":[...],"stream":false}
```
Models used in **direct API requests** are named as reported by ollama.com/api/tags (e.g. `nemotron-3-super`, `mimo-v2.6-flash`, `gemma4:31b`); CLI `:cloud` tags may differ. The native Ollama chat schema accepts `role:tool`, `tool_name`, tool arguments and original source receipt messages. Source: https://github.com/ollama/ollama/blob/main/docs/cloud.mdx and https://github.com/ollama/ollama/blob/main/docs/api.md .

Only the `ollama_cloud_model` and `ollama_cloud_api_key` configuration choose the direct Ollama Cloud service. They are **not** the old `model_base_url`, local `OLLAMA_HOST`, earlier `model_api_key`, or `cloud_api_key` (which is OpenRouter's key).

## V2 Preview configuration

| Setting | Default | Effect |
|---|---|---|
| `cloud_mode` | `free` | Free OpenRouter if `free`; to choose either paid provider set `paid` |
| `cloud_free_model` | `openrouter/free` | Never used as a paid model |
| `cloud_paid_provider` | `openrouter` | `openrouter` or `ollama` when paid mode is enabled |
| `cloud_paid_model` | `google/gemini-3.1-flash-lite` | Existing OpenRouter **paid** model, ignored for Ollama |
| `ollama_cloud_model` | `nemotron-3-super` | Fixed direct Ollama Cloud API model, ignored for OpenRouter |
| `cloud_paid_consent` | `false` | Must explicitly be `true` in *either* paid mode |
| `cloud_api_key` | optional | Existing **OpenRouter** API key; still required for OpenRouter free or paid |
| `ollama_cloud_api_key` | optional | Separate Ollama Cloud key; required **only** for paid Ollama mode |

**Recommended initial setup: stay free until key and credits are ready.**

```yaml
cloud_mode: free
cloud_free_model: openrouter/free
cloud_paid_provider: ollama
ollama_cloud_model: nemotron-3-super
cloud_paid_consent: false
# cloud_api_key: "<secret OpenRouter key>"  (add in Home Assistant options)
# ollama_cloud_api_key: "<secret Ollama key>" (not required while free)
```

**Manually enable paid Ollama Cloud only after you fund or limit usage:**

```yaml
cloud_mode: paid
cloud_paid_provider: ollama
ollama_cloud_model: nemotron-3-super
cloud_paid_consent: true
# ollama_cloud_api_key: "<secret Ollama key>"  (set in add-on options)
```

The UI Configuration editor saves paid consent, and the V2 runtime **fails closed** if a paid key is missing or consent is false. Merely storing the Ollama model/key while `cloud_mode=free` **never** changes provider or incurs Ollama requests. The app does not enforce a monetary spending cap; set Ollama credit/auto-billing limits in the Ollama account before using paid mode. Ollama's public pricing is per token and subject to change: https://ollama.com/pricing . No inference request is made simply to load the settings or System Health UI.

## Privacy and financial controls

All cloud Ask requests send original private home questions, system instructions, live MCP tool schemas and tool-result receipts to the chosen model provider. Only explicit model-choice and full native MCP sources may justify completed answers. A model answer or synthetic tool proposal is not proof of a device state or causal command.

- Native errors and timeouts **never** trigger a retry against the other provider, switch to paid, or replay an uncertain native write.
- Provider API keys remain inside the add-on (Supervisor password fields) and never enter request payloads, browser status, GitHub, logs, or private Technical JSON.
- `model_route.attempted_provider` and status expose the selected provider, paid/free mode and model, not the secret. An Ollama API response supplies optional original durations and input/output token counts, but **not necessarily billed USD cost**; never invent the latter.
- Account credit purchase or Ollama subscription may be separately required for the selected model; the feature itself does not purchase credits.
- An explicitly clicked **AI Evaluation → Test cloud tool calling** performs only one selected-provider model call on a fictitious read-only function. No Hubitat data or native tool action is sent. It **can consume paid tokens** in Ollama paid mode.

## Live testing and quality gate

After installing V2 alpha.90:
1. Validate version and OpenRouter free tool probe first, without real device writes.
2. Manually enable paid Ollama Cloud with a separate key, budget and `cloud_paid_consent: true`.
3. In AI Evaluation, click **Test cloud tool calling**; check the tool call and model/latency. This is a single **synthetic** model round, not live MCP acceptance.
4. Ask one **genuinely new READ-ONLY** native state question. Save PRIVATE first-answer Technical JSON; verify model route `attempted_provider=ollama`, original successful MCP receipts, actual device/attribute/time coverage, model rounds, errors and wall time.
5. Then compare Nemotron 3 Super to MiMo V2.6 Flash and the existing free/paid candidates on genuinely fresh Gate B first answers, scored for factual grounding, source completeness, causal calibration, usefulness, native approval safety, latency and measured usage. Do not declare a winner from published benchmarks or one probe.

**No live Ollama account calls are made by GitHub PR unit tests or CI.** Synthetic regression tests use mock responses and inspect native tool receipts and fixed endpoint requests; installed acceptance needs the owner's private API key.
