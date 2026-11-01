# Q2 — Unscored Claude-reference qualitative review: fixed MQTT source packet

**Date:** 2026-11-01. **Status:** one user-supplied, Claude-attributed first answer; **NOT A MODEL A/B SCORE**. Do not put source claims, review values or raw responses into an official first-attempt scorecard without complete provenance.

## Frozen question and input identity

- Case ID: `aq_network_broker_vs_device_health`, one of 18 existing curated synthetic/anonymised offline packets.
- The prior user-visible comparison prompt contained exact case question: **Why does a disconnected smart plug still show mqttStatus connected?**
- The three model-facing facts in that unchanged fixture are:
  1. The driver's MQTT session to the broker is connected.
  2. The endpoint has stale genuine telemetry and reports offline health.
  3. The driver's watchdog updates the `lastActivity` attribute without endpoint payloads.
- **Verified SHA-256:** `74ccff7fa2c23852655d12b45f6f5cbb6a3315de8c7647cac7b03441282f7150`, independently recalculated from `scripts/answer_quality_fixed_packets.py` canonical payload structure and the actual fixture. This confirms the **prompt text supplied by the assistant matched the registered case**, but does not independently certify what the provider ingested.
- Prior prompt explicitly said **do not call MCP, browse or inspect live systems**; grading/rubric fields were not included.
- The next user message supplied one response attributed by conversation context to Claude. **Claude model self-identified as Sonnet 5.5 in a later reply, with 'as far as I know' caveat. Sonnet 5.5 exists, but serving model, provider logs/tool state, elapsed time and first-attempt provenance were not independently authenticated.** A Gemma 4 31B answer was subsequently supplied from Ollama Cloud; see the new qualitative paired review below. This is not a certified exact-byte input match or an official measured A/B score.

## Source-bounded qualitative review

The answer separated confirmed evidence, the most likely layer distinction, possible watchdog-derived freshness confusion, missing LWT/source packet details and a targeted read-only check.

| Claim class | Assessment |
| --- | --- |
| MQTT driver-to-broker session remains connected | **Supported** by frozen input 1 |
| Endpoint genuine telemetry is stale and health reports offline | **Supported** by frozen input 2 |
| Watchdog updates `lastActivity` without a new endpoint payload | **Supported** by frozen input 3 |
| Broker session can be up while endpoint remains silent | **Plausible direct explanation**, consistent with evidence; not evidence of the physical root outage |
| An unverified consumer may misuse refreshed `lastActivity` as endpoint liveness | **Conditionally sound; clearly qualified** as not established by the packet |
| Offline health `reflects the plug's state` / is `the value to trust` | **Some overstatement risk:** offline health is the reported telemetry-based status; **physical power/connectivity is not independently verified** |
| LWT/availability publication, subscription, and last physical payload time | Correctly stated as **unknown** |
| Comparing genuinely sourced endpoint telemetry with watchdog `lastActivity` | **Useful read-only discriminator**, no test or operation claimed performed |

**Judgement:** The response is concise and substantially aligned with the known packet. One statement could be sharpened to avoid treating a driver-reported health state as independently verified physical reality. This is a human **qualitative source review**, not numeric/percentile scoring, proof of Claude superiority or an independently certified first-attempt benchmark.

## Comparison and safety boundaries

- This is **one Claude-attributed response for one frozen offline packet**. A v0.18.331, v0.18.332 or v0.18.333 HomeBrain *live device* response uses entirely different evidence, and **must not** be presented as a paired Gemma answer.
- The user has now supplied a **Gemma 4 31B direct Ollama Cloud answer** to the same question, packet identifier and three facts. The command used a no-tools, single user message with `temperature:0`; prompt spacing/layout differed slightly from the earlier Claude rendition, and the provider request/response and Claude settings were not independently attested. See the qualitative source-by-source comparison below. Raw responses remain private.
- The reported Claude Sonnet 5.5 identity is **self-reported, not authenticated**; actual model, first-attempt status and tool settings remain unverified. Do not fabricate these fields or infer elapsed time.
- Published metric remains **NOT MEASURED** and **0 fully authenticated, exact-input, blinded cross-model A/B pairs**. One source-matched two-model qualitative comparison exists; it is informative but does not satisfy the strict protocol.
- No model API calls, network reads, device control, live Hubitat/HA modifications or private household records were used in this review.

## Next engineering gate

Use this response as a **qualitative target**, not a canned MQTT answer. Evaluate why HomeBrain's source-grounded model-to-finalizer boundary replaces natural explanations with long diagnostics across **at least telemetry, historical command/report attribution, and heating**. Compare original, attested model outputs to final published outputs on the same source packet, with zero unsupported physical/cause claims. Only then consider any general model-first publication promotion.

## Correct Ollama Cloud comparison target (2026-11-01)

The user's HomeBrain runtime uses **Ollama Cloud Free** with Gemma 4 31B (not a local NucBox model used in an illustrative Claude command). Ollama's official Cloud API documentation says to use HTTPS `https://ollama.com/api/chat` with bearer `OLLAMA_API_KEY`, and API model name **`gemma4:31b`**; `gemma4:31b-cloud` is used with the installed Ollama app/CLI. A command using `gemma3` and `http://<nucbox-ip>:11434` would **not** test this model/provider. Sources: <https://docs.ollama.com/cloud>, <https://ollama.com/library/gemma4:31b-cloud> (reviewed 2026-11-01).

No API keys, tokens, household logs or private answers are committed. The participant must execute any benchmark call themselves, retaining their key outside source control and chat. The comparison must use the full **identical original rendered prompt**, not just matching evidence facts. Disclose different temperature/sampling/model settings as comparison limitations; do not treat a `temperature:0` Gemma call as identical Claude sampling.

## 2026-11-01 — Gemma 4 31B direct Cloud answer received: first source-matched qualitative pair

The user repaired Termux's `curl` / `libngtcp2` version mismatch and executed a direct `https://ollama.com/api/chat` request, with model `gemma4:31b`, `stream:false`, `options.temperature:0`, a single user message, no supplied model tools and the unchanged packet identifier. The captured output was a short answer with sections for confirmed observations, possible explanation, unknowns and next read-only check. It did not contain an Ollama provider request ID, complete raw HTTP receipt, elapsed wall time, or independent confirmation of first-attempt status. No API key was included in the captured result.

**What is actually comparable:** Both user-supplied responses used case `aq_network_broker_vs_device_health`, the same question, three substantive source facts and instruction not to use other tools. The Claude prompt shown earlier and the Termux command sent to Gemma had **minor layout/blank-line differences**, so their full transmitted prompt text was **not proven byte-identical**; Claude's decoding settings and provider selection are unverified. The canonical hash identifies the fixture content, **not** independent byte-level identity of the entire sent message.

| Evidence obligation / quality dimension | Claude Sonnet 5.5 (self-reported) | Gemma 4 31B (Ollama Cloud, user command) |
| --- | --- | --- |
| Broker-session vs device-liveness | Clearly distinguished; supports the explanation | Correctly identifies possible link distinction; more tentative |
| Stale endpoint telemetry and offline health | Supported reported-state interpretation | Correctly enumerated as observed |
| Watchdog-updated `lastActivity` without payload | Explains that downstream freshness checks could be misled, conditionally | Notes fact but **does not explain the misleading-freshness consequence** |
| Physical outage mechanism | Not proved; slight risk in treating reported health as physical truth | No physical causal invention |
| Unknown implementation or source | Notes LWT/availability and genuine last-packet timestamp as unknown | Notes actual `mqttStatus` mapping as unverified despite broker-session evidence |
| Read-only next discriminator | Compare last genuine endpoint telemetry with watchdog `lastActivity` | Verify driver source/config's `mqttStatus` mapping |
| First answer communication | More directly connects all evidence into an explanation | Concise, sound and conservative, but comparatively shallow |
| Unsupported definitive causal claim | No conclusive network/power cause identified | No conclusive network/power cause identified |

**Qualitative judgement:** The Gemma response is concise and stays within the supplied evidence, establishing that the model can offer a readable, no-tool answer outside HomeBrain's finaliser. Claude's answer does a better job converting the third fact into a user-useful consequence and prioritising a discriminator, albeit with a mild physical-state overstatement. This **does not prove** a universal model capability ranking, actual source-method behavior of the user's physical driver, quality rates, or that disabling HomeBrain's finaliser would be safe for lighting/heating/causal cases.

**Engineering inference:** Before modifying production publication, distinguish the actual model draft from an already-repaired `outcome.message` (the v0.18.334 `publicationBoundaryShadow` explicitly says incoming raw provenance is unverified), then compare draft versus published messages on the **same source receipts** across device telemetry, lighting attribution, heating and source-gap negatives. Preserve independent causal-claim validation and read-only/write separation; do **not** promote free-form model assertions based on this one benign status question.

**Official quality status:** 18 curated fixed offline source packets, 13 legacy targets, **one source-matched qualitative pair**, **0 independently certified exact-byte frozen first attempts**, no reliable matched wall-time comparison; formal scorecard remains **NOT MEASURED**.
