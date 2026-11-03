# v0.18.386 — Source-coverage inventory versus rule-execution investigations

## Installed after-result driving this change

A read-only request to identify the native Rule Machine parent, list existing one-time rules, and *explain why identity remained unverified* was answered by installed v0.18.385 in **25.65s**, with six Gemma 4 31B free rounds and ten logical tools. It identified the **candidate** parent ID 169 from an app list, but described namespace `hubitat` as an interpretation, failed to read built-in Groovy source for class 18, and asserted **42 one-time rules** when the returned diagnostic receipt only established that an ordinary rule inventory had been retrieved. No thin `hub_get_app_config(appId=169,summary=true)` request appeared in the technical tool records. The actual MCP server version and native parent class therefore remain unverified.

The published answer's positive "Success" label did **not** prove its central claim. The evidence is a single real answer/technical-JSON sample; `model_delivery_verified`, `first_attempt_verified` and `deployed_build_sha_verified` were false, so this is *not* a certified population accuracy score.

## General source-selection correction

The read-only typed inventory classifier previously treated any bare `why` as a request to investigate past execution and bypassed the existing no-extra-model-round native inventory path. It now treats **cause/execution/action questions** (why a rule ran, triggered, turned off, was cancelled, etc.) as deep reviews while allowing **source identity/coverage explanations** to use the existing source-typed inventory path. The native inventory projector already supports the strict flat MCP 5.1.5 installed-app summary, so no new network tool or runtime writer was added.

The deterministic inventory answer now includes the verified **Rule Machine type and `namespace=hubitat`** only when an exact native class join or independently source-typed summary supports it. Absent/contradictory identity remains explicitly unverified. Only rule names matching the exact one-time suffix can be called one-time; a `Rule-5.1` type or an overall rule count cannot prove one-shot scheduling.

## Tests, limits, safety

Synthetic tests cover the exact question shape, source-only "why unverified" versus actual rule-execution questions, a thin namespace-returning MCP read, one-time versus ordinary rule listing, and no model calls, Groovy source reads, writes or device changes for an inventory objective. The installed before observation was **25.65s / 6 model rounds**; offline after **no model rounds for recognized inventories**, but **no real post-install latency or answer-quality improvement is yet measured**. No live Hubitat, Home Assistant or OpenWrt changes were made during development; the dated BAT writer remains disabled.

Risk: overly broad inventory classification could hide a genuine execution investigation. Explicit causal/action verbs remain deep and are tested. Rollback: revert this PR. After green CI and installation, obtain one fresh read-only natural answer + full technical JSON for the native Rule Machine identity/inventory question; require source-backed `namespace` before considering a separately authorized disposable virtual-switch scheduled test.
