# Q1 broad hub health — installed v0.18.404 live review (2026-11-04)

## Frozen live input and source scope

One new HomeBrain topic received the exact registered, read-only
`broad_hub_health` question: **What is the hub health status?**
The user supplied the published answer and complete Technical JSON.
Installed reported add-on version: **0.18.404**; provider
`ollama-cloud`, model `gemma4:31b`, selected free tier.

The answer used one successful `homebrain_hub_info_snapshot(scope=full)`
receipt, evidence kind `authoritative_hub_info_snapshot`,
source type `hub_information_driver`, source scope matched.
It reported 18 typed scalar fields. At **2026-11-04T16:41:14.558120Z**
the one snapshot reported five-minute CPU load **0.67**,
`cpu_percent=16.75`, free memory **767.41 MB**, database size **163 MB**,
uptime **0d:22h:39m:22s**, firmware installed/available both
**2.5.3.117**, Zigbee enabled and source-reported healthy,
Z-Wave disabled, Matter online. The response correctly withheld
temperature because no temperature value was supplied, despite
`temperature_unit=°C` appearing. It qualified external firmware
freshness and did **not** infer a physical fault or complete health.

**Source limitations:** The single driver scalar snapshot contained no
verified alert/warning inventory or stale-log review, no independent
attribute source timestamps, and no independent physical/system health
attestation. An `outcome=success` label means the answer route succeeded,
not that the fixed benchmark's *live metrics and alerts* obligation was
fully satisfied. CPU load and a separately labelled CPU percentage were
reported, but the driver receipt alone does not independently verify their
calculation equivalence. Zigbee `healthy=true` is the driver's string
attribute, not an independent Zigbee mesh performance test.

## Performance / model boundary

- Measured one-request wall `elapsed_ms=9376` (**9.376s**) meets
  charter's under-15-second routine status target **for this sample**.
  No repeated-sample median or p95 exists.
- **2 Gemma rounds**, provider **3019ms**, **1 source tool call**,
  `tool_discovery_calls=1`, `local_tool=6021ms`,
  `mcp_http=6323ms`. These timing scopes may overlap;
  do not sum them into the total request.
- The snapshot diagnostics say one poll read, no poll sleep, two refresh
  commands, and settled firmware status. These are driver
  refresh diagnostics inside a read-classified tool receipt; they are
  *not* independent proof of endpoint or device writes and merit source
  review before optimising snapshot latency.
- `typed_status_source_claim_repairs=4` is a counted boundary metric,
  not evidence that the raw model was factually correct. No
  `publishedIsFirstModelDraft` or equivalent first-draft attestation
  was supplied in this request. Explicit
  `model_delivery_verified=false`, `first_attempt_verified=false`
  and `deployed_build_sha_verified=false`. Do not score independently
  correct model-first answers or deployed SHA based on this receipt.
- `success=true`, `outcome=success`, no write tool receipt; no
  Hubitat/HA/router/device/rule changes requested or evidenced.

## Case acceptance / next direction

**Partial Q1 pass.** Driver-backed current metrics, calibrated
uncertainty and an under-target measured wall-time are established.
The alert-inventory and stale-log dimension of the fixed
`broad_hub_health` case remains **not covered**, rather than
automatically passed. No unsupported definitive causal diagnosis was
identified in the *published* natural-language answer.

Do not add a one-off hub-health phrase patch or claim full system
health from scalar fields. Keep this bounded source-coverage gap
available for cross-domain Q1 source-selection review. Q1 now has
one paired MQTT source/latency case and one different-domain
hub-health live observation. Advance to **Q2 same-evidence A/B
reasoning**, using the existing frozen offline packet protocol:
actual first-model answers, identical source packets, pinned settings,
private SHA-bound human source review, no invented Claude output or
unsolicited paid calls. Quality scores and p50/p95 remain
`not_measured` until genuine samples exist.
