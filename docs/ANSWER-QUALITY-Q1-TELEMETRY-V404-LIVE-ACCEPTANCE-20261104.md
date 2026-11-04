# Q1 MQTT/health — installed v0.18.404 live acceptance (4 November 2026)

## Grounded observation

A user-supplied first, read-only live run of the **unchanged** registered
`device_mqtt_conflict` question on installed add-on version **0.18.404**
returned an appropriately unresolved explanation. This is the same frozen
question used for the single-run v0.18.402 and v0.18.403 comparisons.
No HomeBrain, Hubitat, HA, router, device or automation write was requested.

The final published answer distinguished Hubitat-reported
`healthStatus=offline` from `mqttStatus=connected` without treating
the broker/session report as proof of live endpoint packets or physical
connectivity. It acknowledged the divergent telemetry clocks
(`lastSeen` implied **567.9h** at read; `dataAgeSeconds` **45.1h**;
`sourcesAgree=false`), and withheld specific driver/watchdog, physical
reachability and network-fault claims. A 24-hour bounded history returned
13 mixed device/driver-origin records, including reported MQTT disconnect
and reconnect events, and no command invocations. This is NOT complete
historical coverage or independent endpoint-packet evidence. The most recent
`deviceHealth=unknown` history record is a *reported attribute event*,
not a direct physical check.

The technical coverage remains `outcome=unresolved`,
`evidenceComplete=false`, `rootCauseVerified=false`,
`verifiedInstalledDriverBehaviour=false`,
`independentBrokerPacketsVerified=false`,
`physicalCommunicationVerified=false`,
`historicalWindowComplete=false`. Source classes for target state,
bounded history and target-scoped logs were checked. A checked class
is not a proven upstream cause.

## Paired performance — observed individual requests, not p50/p95

| Installed version | Wall-time | Model rounds | Tool calls | Provider time | Published explanation |
| --- | ---: | ---: | ---: | ---: | --- |
| v0.18.402 | 36.507s | 6 | 8 | 29.747s | Unverified definitive physical/driver claims |
| v0.18.403 | 42.635s | 8 | 13 | 35.241s | Grounded after publication guard |
| **v0.18.404** | **29.023s** | **6** | **7** | **21.780s** | Grounded after publication guard |

v0.18.404 compared with v0.18.403: **-13.612s wall-time
(-31.9%)**, **-2 model rounds**, **-6 tool calls**, **-13.461s
provider time**. Compared with v0.18.402, wall-time was 7.484s
shorter. These are **single different-time live observations**,
not controlled distributions or a proof of attributable speedup.
The complex investigation wall-time is below the charter's
preferred 45-second target on this one run only.

## Instrumentation and source integrity

- `telemetry_post_read_sufficiency_stop=1` — the new bounded
  completion gate fired with target-matched evidence.
- `telemetry_source_claim_repairs=2`, categories:
  `telemetry_driver_claim_unverified` and
  `telemetry_clock_claim_unverified`. Thus the published
  factual language needed two source-boundary repairs.
- `publicationBoundaryShadow.replacementPerformed=true`,
  `modelFirstDraftBoundary.publishedIsFirstModelDraft=false`,
  `rawDraftSourceClaimsAttested=false`,
  `model_delivery_verified=false`,
  `first_attempt_verified=false`,
  `deployed_build_sha_verified=false`.
  Do not score this as raw Gemma first-draft reasoning correctness
  or deployed commit-SHA verification.
- Seven read-only tool receipts covered targeted resolution/state,
  target-scoped logs, 24h history and a legitimate device configuration
  read. The prior invalid attempt to treat verified *device* ID 7103
  as a Groovy *app* ID was not observed.
- A UI displayed about 29.0s and the JSON reports `elapsed_ms=29023`;
  provider `21780ms`, agent `timings_ms.total=25244`.
  Treat separate timing fields as differently scoped, not additive.

## Acceptance decision and next milestone

**Accept Q1 v0.18.404 as one successful published-answer grounding
regression and one observed wall-time improvement.** It did not
verify endpoint health, installed driver internals, independent
first-draft reasoning, p50/p95, or the root cause. No further
device-specific guard is justified by this result.

Do **not** repeat the same MQTT device case again for another
iteration. Continue the fixed Q1 inventory using the distinct,
read-only `broad_hub_health` case in a new HomeBrain topic:
`What is the hub health status?`
Capture one complete natural answer and Technical JSON, assessing
fresh hub metrics and alerts, evidence provenance, historical-log
freshness, unsupported causes, latency, model rounds and tool calls.
Then advance toward same-evidence Q2 model A/B comparisons.
