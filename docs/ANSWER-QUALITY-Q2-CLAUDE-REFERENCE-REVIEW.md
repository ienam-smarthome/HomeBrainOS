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
- The next user message supplied one response attributed by conversation context to Claude. **Claude model self-identified as Sonnet 5.5 in a later reply, with 'as far as I know' caveat. Sonnet 5.5 exists, but serving model, provider logs/tool state, elapsed time and first-attempt provenance were not independently authenticated.** No Gemma response to the same frozen packet has been received.

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
- Require a **Gemma first-attempt answer using the identical question, packet SHA, three source facts and no-tools policy**, and disclose model/provider. Capture a private raw response (not in this repo) before blinded factual/clarity review.
- The reported Claude Sonnet 5.5 identity is **self-reported, not authenticated**; actual model, first-attempt status and tool settings remain unverified. Do not fabricate these fields or infer elapsed time.
- Published metric remains **NOT MEASURED** and 0 completed cross-model A/B pairs.
- No model API calls, network reads, device control, live Hubitat/HA modifications or private household records were used in this review.

## Next engineering gate

Use this response as a **qualitative target**, not a canned MQTT answer. Evaluate why HomeBrain's source-grounded model-to-finalizer boundary replaces natural explanations with long diagnostics across **at least telemetry, historical command/report attribution, and heating**. Compare original, attested model outputs to final published outputs on the same source packet, with zero unsupported physical/cause claims. Only then consider any general model-first publication promotion.

## Correct Ollama Cloud comparison target (2026-11-01)

The user's HomeBrain runtime uses **Ollama Cloud Free** with Gemma 4 31B (not a local NucBox model used in an illustrative Claude command). Ollama's official Cloud API documentation says to use HTTPS `https://ollama.com/api/chat` with bearer `OLLAMA_API_KEY`, and API model name **`gemma4:31b`**; `gemma4:31b-cloud` is used with the installed Ollama app/CLI. A command using `gemma3` and `http://<nucbox-ip>:11434` would **not** test this model/provider. Sources: <https://docs.ollama.com/cloud>, <https://ollama.com/library/gemma4:31b-cloud> (reviewed 2026-11-01).

No API keys, tokens, household logs or private answers are committed. The participant must execute any benchmark call themselves, retaining their key outside source control and chat. The comparison must use the full **identical original rendered prompt**, not just matching evidence facts. Disclose different temperature/sampling/model settings as comparison limitations; do not treat a `temperature:0` Gemma call as identical Claude sampling.
