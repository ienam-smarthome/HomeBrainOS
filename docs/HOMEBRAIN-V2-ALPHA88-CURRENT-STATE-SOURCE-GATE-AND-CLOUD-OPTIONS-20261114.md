# HomeBrainOS V2 alpha.88 — explicit current-state source sufficiency

**14 November 2026 — V2 only, model-led native MCP. No change to V1, hardware, native approval or provider routing.**

## Source-real motivation

An independently owner-captured local Qwen `qwen3.5:4b` alpha.87 read-only first answer to a current reported device-state question returned a text-only plan asking the user to authorise a read. Original PRIVATE Technical JSON recorded **zero MCP calls**, **zero prior receipts**, a read-only catalog with 40 native read tools, one completed local model round and about **34.4 seconds** elapsed. The model claimed catalog-based target identification but did not actually inspect the device, making factual/source completeness and usefulness 0/2 on the owner's manual review. There were no writes and no MCP errors. The private question, raw identity, receipts and household details remain outside GitHub.

The preceding alpha.86 local first-round timeout (120 seconds without a model reply) was improved as an execution problem by alpha.87's no-thinking / 8K local model settings, but the alpha.87 result demonstrates that **a completed model response does not guarantee source-backed autonomous work**.

## One transferable V2 improvement

For **explicit live/current state queries** (e.g. ask for current device status, reported temperature, active sensors), if the first proposed final answer contains **no tool receipts** and a live read-only tool is available, offer one **model-led** source-completion checkpoint. The model—not the host—decides which actually advertised read-only tool to call, its target/arguments or that no safe proportional source is available. The prompt reminds it that source catalog visibility is NOT device identity, that a read already has permission and that a state/field timestamp requires an original receipt.

- The recovery is **single-use, bounded by the existing request deadline**, and restricted to live catalog tools with read-only contracts; the prompt and host do not select or execute a new MCP call. An unsolicited mutating proposal is rejected without execution.
- No added checkpoint for device-control writes, generic knowledge, status explanations without explicit live intent, or source-result responses. Historical and causal review contracts retain their existing logic.
- Does not add another final text-audit round for the simple current-state checkpoint, limiting extra latency on local models.
- Private Technical JSON records `source_review_kind=current_state` and `current_state_source_status` as either `read_only_receipt_present` or `no_source_read_receipt`. A returned read is **not necessarily the correct target or a fresh observation**; only manual review of original source can establish correctness. Ask UI flags when this checkpoint still produced no successful read receipt, rather than presenting prose as verified state.
- Original source receipts remain unchanged and no model answer is rewritten automatically. Model interaction still enforces all existing device write approvals and read-only restrictions.

**Costs and risk:** The extra model prompt is sent **only when this failure condition occurs**, and consumes a full extra inference round/credits if the model is cloud-hosted. On the local 4B, a second round might add tens of seconds and may still fail to choose a tool. This is a hypothesis plus fictional orchestration tests—not evidence that Qwen is a suitable autonomous agent. Installed new read-only acceptance is mandatory.

## Local vs free and paid cloud: evidence-led priority

The owner-observed local inference processed 4,098 prompt tokens in 17.83 seconds, then 126 output tokens in 7.17 seconds, plus roughly 8.85 seconds model load, **34.09 seconds Ollama time and 34.39 seconds request end-to-end**. It performed no MCP call. This is one observation, not a benchmark for other devices or future warm runs. A multi-round HomeBrain investigation could take several minutes locally; thinking disabled has not yet established adequate natural multi-source reasoning.

Verified public pricing as of November 2026:
- OpenRouter `openrouter/free` and explicit `:free` models: $0 token price; **50 requests/day** on an uncredited account, and each MCP dialogue may consume several model requests. Models/rate limits/quality are not stable. Source: https://openrouter.ai/collections/free-models
- OpenRouter `google/gemini-3.1-flash-lite`: **$0.25 input / $1.50 output per 1 million tokens**, advertises OpenAI-compatible tool calling. Source: https://openrouter.ai/google/gemini-3.1-flash-lite
- OpenRouter `deepseek/deepseek-v3.2`: advertised tool calling on supported providers, token price varies by routing/provider; approximately $0.21+ / $0.31+ per million in one observed public result, not a durable ceiling. Source: https://openrouter.ai/deepseek/deepseek-v3.2
- Gemini Developer API has free tiers for some Flash models, subject to model/rate limits and free-tier data-use terms; paid tier differs. Source: https://ai.google.dev/gemini-api/docs/pricing
- OpenRouter Standard supports API key spending controls and provider-specific pricing, with platform fees where applicable. Source: https://openrouter.ai/pricing

**Illustrative token cost** for 40,000 input and 1,000 output tokens in total at Gemini 3.1 Flash-Lite prices: 40,000 / 1,000,000 × $0.25 + 1,000 / 1,000,000 × $1.50 = **$0.0115** before any platform, provider or applicable taxes/fees. It is an estimate, not current HomeBrain usage because V2 has not yet reported complete cloud token billing across rounds. A 100-investigation month at that hypothetical usage is **$1.15** before fees. Actual cost can be higher with long receipts, retries, more rounds or another model.

### Recommendation / boundary

Treat local Qwen as a **secondary/offline-only path** until source-real tool-calling acceptance improves. Prioritise benchmarked cloud reasoning quality, a free-model route and an explicitly authorised **pre-funded low-cost paid** model for reliability. Keep source privacy in view: sharing original Hubitat MCP receipts with OpenRouter/free-provider is an external disclosure; never enable it silently. Prefer account-side, per-key credit/spend caps and an explicit named paid model. **Do not implement automatic free→paid escalation, recurring billing, unbounded retries or an automatic financial charge in this release.**

The existing V2 alpha.87 router supports local Ollama primary and *opt-in free cloud backup on initial local connection failure*, **not** a paid primary/free→paid automatic router. Introducing cloud-primary and optional paid fallback needs a separate deliberate provider-selection configuration, OpenAI-compatible tool calling, private disclosure messaging, cap/error audit and **source-real first-answer quality checks**. It must not break V1 or auto-replay writes on provider failure.

## Fictional checks and installed acceptance

Unit tests cover explicit live-state intent without tool receipt, one model-selected read after the checkpoint, source status provenance, prompt rejection of unnecessary read permission, single-use fallback, and refusal of a write in the read-only review. Current noncausal simple answers and causal/historical mechanisms remain unchanged. Synthetic CI only proves the control flow.

After upgrade, ask a genuinely new **read-only** current-state question (not the exposed original case). Inspect original MCP tool receipts, `source_review_kind`, source status, model rounds, duration and fidelity of the answer. Do not interpret a returned tool as successful state identification unless the original response supports the requested target, attribute and freshness. Continue Gate B with fresh multi-domain investigations and separately compare free/paid clouds against local. Defer live writes until each model demonstrates reliable read-only behavior.
