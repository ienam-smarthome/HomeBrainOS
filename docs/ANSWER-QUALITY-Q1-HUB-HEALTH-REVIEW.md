# Q1 — installed hub-health answer, source-bounded review

**Date:** 2026-11-03 · **Case:** `broad_hub_health` (registered legacy task)
**Installed add-on self-report:** `v0.18.382` · **Request:** `What is the hub health status?`
**Review:** qualitative, source-bounded, **not a certified first attempt or full source grade**

## Registered-question check

The received `request_provenance` had source `api_ask_request`, normalization `collapse-whitespace-v1`, SHA256 `b586998f15c01644355754722ae36cce273a5026d2c436046e6a441b05ebf23c`. Independently recomputing SHA-256 of the registered question produces the same digest. This is evidence that the **installed API reports it received the registered question**, not proof of unchanged model input. It explicitly sets `model_delivery_verified=false`, `first_attempt_verified=false` and `deployed_build_sha_verified=false`. Do not count as a confirmed first-useful answer.

## Real execution and answer

The user supplied one concise hub-status answer containing firmware, CPU, available memory, temperature, uptime, database size, Zigbee, Z-Wave and Matter fields. There were no modifying Hubitat tool receipts. The result reported `route=unified-mcp-agent`, `request_class=live-read`, `intent=native-function-calling` and model `gemma4:31b`; it was **not a model-free deterministic health route**. Two free Ollama Cloud model rounds were recorded. The final wording's attribution to the model versus host presenter was **not independently verified**; do not infer it from model usage.

The only evidence receipt was `authoritative_hub_info_snapshot` with `success=true`, `supports_live_claim=true`, `scope=full`, read/nonmutating effect and a field-name-only summary. Source selection is plausible and appropriate for the question, but **individual returned scalar values were absent from the public receipt**. Therefore an independent reviewer cannot yet certify the reported individual numerical values, `up to date`, `no active alerts` or the radio statuses from that JSON; the model answer and the source success flag are not sufficient independent proof. No source-invented claims or fabricated failures should be inferred from the lack of receipts.

**Latency:** 17,425 ms wall / 17,383 ms agent, above the charter's 15,000 ms common-status target; 4,987 ms cumulative model provider, 9,991 ms local snapshot, 2,385 ms discovery. Reported cumulative MCP HTTP 12,369 ms **overlaps** tool-phase accounting; do not add all these into a synthetic elapsed time. One observation does not establish a median, p95, repeatability, source incident or causal bottleneck. The Hub Info tool performs its documented refresh/update-check and bounded polling; the technical receipt did not report the number of internal polls.

## Provisional outcome

| Dimension | Finding | Formal Q1 scored? |
| --- | --- | --- |
| Registered API question | Exact SHA-256 match | Request-match eligibility only |
| First attempt | Not independently authenticated | No |
| Source selection | One successful authoritative driver snapshot | Provisional only |
| Value-level grounding | Cannot independently verify from field names | **Not measured** |
| Naturalness/readability | Concise, clear operator-facing status | Qualitative only |
| Causal certainty | No historical causal claim tested | Not applicable |
| Status latency | 17.425s wall, exceeds 15s target for this sample | One observed sample |
| Safety | Read-classified evidence; existing internal refresh/check behaviour | No demonstrated config mutation |

This case is a **real Q1 evaluation observation**, not an official pass/fail for the 90% source-grounding or 80% useful-first benchmarks and not a same-packet model A/B. The source-complete value-level packet and deployed commit attestations were not available in this historical response.

## General development decision

v0.18.383 introduces a bounded allowlisted Hub Information Driver *receipt projection*, plus same-call poll diagnostics. It changes neither the model-led question route nor the general response text, and does not shorten or parallelize any refresh actions based on a single response. Once installed, the projection may allow future status answers to be source-reviewed from their own technical JSON. No after-result is claimed until real acceptance. The permanent Q1/Q2 roadmap continues; Internet-blocker work stays paused.
