# Q2 — four-domain local first-answer review: source coverage versus latency (4 Nov 2026)

**Scope:** Four *different* frozen synthetic/anonymised evidence cases evaluated in four user-executed, local-only Qwen3.5:4b vs Llama3.2:3b first-answer pairs. No real device, rule, Router, Hubitat, Home Assistant, paid Cloud API or production publisher run is represented here.

**Interpretation:** The measurements below come from user-pasted `baseline.json`/`candidate.json`, not independent verification of provider processing or system state. Cross-case runs occurred on **different checked-out revisions of the offline evaluator** and at different times; however, *within each pair* both models received the same frozen source packet and runner configuration. Model-request timing is not an end-to-end user-visible HomeBrainOS latency and these four cases do not establish a robust median, p95, model reliability rate or general superiority. Each manifest records `attempt_index=1` for its own run.

## Actual per-case observations

| Frozen case / domain | Qwen local | Llama local | Source-based first-answer assessment |
| --- | ---: | ---: | --- |
| `aq_network_broker_vs_device_health` — MQTT | **20.344s** | **8.531s** | Qwen distinguishes broker session, stale endpoint and watchdog-written lastActivity; Llama addresses broker/endpoint separation but omits the watchdog discriminator |
| `aq_command_issuer_vs_reporter` — causal OFF | **26.344s** | **10.594s** | Qwen finds command issuer vs bridge reporter but overclaims command receipt/cause and saved text ends mid-heading; Llama falsely concludes prior OFF, device command receipt and that recorded command issuer app 4012 did not initiate it |
| `aq_early_heating_off_resume` — setpoints | **22.672s** | **6.406s** | Qwen gives 12°C override/30min 22°C restoration/independent demand but invents frost safety floor and heartbeat, omits explicit boiler-operation limitation; Llama provides only the 12°C setpoint, omitting all other obligations |
| `aq_rule_parent_type_gap` — native class | **19.657s** | **8.297s** | Both leave native RM parent unverified; Qwen notes missing built-ins and source name gap, but suggests only a fuller catalog instead of requiring direct source-attested native class binding; Llama states a correct caution but infers the system might not recognise RM type, which is not evidenced |

**Descriptive model-request latencies, four samples each:**
Qwen arithmetic mean **22.254s** (unrounded mean 22.25425s); Llama arithmetic mean **8.457s**. Relative summed times give ~**2.63×** ratio. Report these as descriptive properties of exactly four samples, **not** provider speed SLAs or statistical latency percentiles. Llama was faster on **all four recorded cases**, but at the cost of serious missing evidence and/or incorrect causal logic. Qwen covered more source details on each review, yet still issued unsupported conclusions and returned at least one visibly truncated text.

**Captured identity:** Individual fixed packets, answer hashes, build SHAs, provenance limits and qualitative reviews for the first three cases are documented in earlier case-specific notes:
- [MQTT first local pair](ANSWER-QUALITY-Q2-FIRST-LOCAL-MQTT-PAIR-20261104.md)
- [Command provenance](ANSWER-QUALITY-Q2-LOCAL-COMMAND-ATTRIBUTION-20261104.md)
- [Heating](ANSWER-QUALITY-Q2-LOCAL-HEATING-PAIR-20261104.md)

## Final fourth case — exact Rule Machine parent identity

**User-provided case metadata:**
- Case `aq_rule_parent_type_gap`; packet SHA
  `21542170532d34510b19613f6c7bd97958cf300aa8cf151e2649ef8328b14cf3`.
- Same local checkout SHA for both arms:
  `659d3a3e3373b654a54439b37461a9e237aa2289`.
- Qwen `ollama-local/qwen3.5:4b`, 19,657 ms, recorded answer SHA
  `3511c0f2604d4cbfcb0e5d7e1e76deb8ca9a3a776bc4a56d87a1fcf5af17aa96`.
- Llama `ollama-local/llama3.2:3b`, 8,297 ms, recorded answer SHA
  `b8ee24d20674fb6d932027d11188cdc81e8b8d4b1078ea84ea5ecf8d221d5ca6`.

The question is whether instance 901 may be treated as a **verified native Rule Machine writer parent** given that it is display-labelled Rule Machine with appTypeId=718, the returned type-class list omits built-in classes and has no row for 718, and the name does not prove typed namespace identity.

**Qualitative assessment of the visible Qwen first answer:**
Correctly reports all three facts and says class resolution/verification is blocked by missing catalog information. It speculates on why built-ins are missing, which is expressly unknown, and proposes reading a complete catalog. It does not unequivocally assert that a *direct, source-attested identity relationship* between instance and native class is required; a fully populated catalog alone may still not prove writer-parent identity. It does not claim native RM is absent, nor fabricate verified identity.

**Qualitative assessment of the visible Llama first answer:**
Correctly says a parent is not verified and recognises catalog omissions. Its claim that the system is **not recognising** Rule Machine type is not established; incomplete returned class inventory is a measurement limitation, not necessarily a runtime type-recognition failure. The suggested catalog check is relevant but insufficient to establish a native writer-parent class binding. It omits instance 901/type 718 and the required explicit *missing catalog cannot prove type absence* statement.

**Original-file integrity check resolved (user-executed PowerShell, 2026-11-04):**
An earlier SHA-256 calculated over the **pasted Llama prose**
(`f88b1baf1eb1ead58147fb778a4b91ec7138b7ed933acc8abe631ff2c783b346`)
differed from the manifest; this was a **pasted-text representation mismatch**, not an observed corruption of the benchmark output. The user subsequently located the original private Rule Machine capture folder and ran `Get-FileHash -LiteralPath (Join-Path $PrivateDir "aq_rule_parent_type_gap.candidate.txt") -Algorithm SHA256`.
The result was exactly
`b8ee24d20674fb6d932027d11188cdc81e8b8d4b1078ea84ea5ecf8d221d5ca6`,
**matching the original `candidate.json` SHA-256**. A subsequent UTF-8 read displayed the same substantive Llama explanation. The saved local file's byte integrity relative to the user's manifest is therefore **confirmed by the user's independent local file-hash check**. The exact originally pasted formatting remains non-byte-identical, so do not claim that *the paste itself* matches the digest.

The user-visible Qwen pasted text independently matched its saved-answer SHA `3511c0f...`. Neither file check independently attests provider model identity, source ingestion or answer accuracy. This resolves the **saved-file digest** blocker but does not substitute for a completed source-grounded human review rubric.

**Grounded minimum response for the fourth case:** App 901 is only a *candidate* native RM parent. The missing type 718 row in a catalog known to omit built-in classes does **not** establish that type 718 does not exist. An independently source-attested mapping from instance 901 and type 718 to the built-in native Rule Machine class is required before claiming verification or authorizing native Rule Machine writes. No rules are created by this benchmark.

## What the full four-case comparison means

- **Current local model choice:** No global winner can be declared. If source completeness is more important than raw speed in local fallbacks, Qwen appears more promising than Llama on these four paired examples, but neither may be trusted to invent command delivery, boiler operation or native writer identity.
- **Common cross-model failure dimensions:** unsupported causal bridging (command → report → execution), limited source completeness, unverified mechanism explanations, and text completion under a small fixed output budget. These are general categories for future measured architecture/model/prompt evaluation, **not** permission to introduce single-phrase repair patches.
- **Measured/unmeasured boundary:** This is an assistant source-based **qualitative comparison** with actual user-provided first outputs; no independently completed blinded human rubric, no official grounding or useful-first percentage, no sample-supported p95, and no Gemma-vs-local cross-domain comparison. The single Gemma Cloud vs Qwen MQTT result is separate and should not be merged into the four-model-local latency arithmetic.
- **No production change:** HomeBrainOS add-on remains `v0.18.404`. The project must preserve read-only safety and current model routing pending broader, genuinely reviewed A/B experiments.

## Next acceptance tasks

1. **Complete:** The user's original local Llama Rule Machine answer file SHA matches the existing manifest exactly; no further model inference or file integrity checks are required for this case.
2. Consider source-backed **independent human SHA-bound pair reviews** for the four cases (not synthetic grades). Four pairs alone do not establish broad benchmark acceptance thresholds; publish accurate denominators and `not_measured` wherever appropriate.
3. Use at least one new **read-only live HomeBrain Q&A with its diagnostic JSON** or a clearly consented fixed-packet Gemma Cloud cross-domain comparison to separate model reasoning gaps from real evidence-tool/source selection and publisher behaviour. Prefer the former before editing runtime code. Cloud runs require explicit billing/usage consent.
4. Only after evidence review decide whether to experiment with model choice, source contracts or simplification. Keep command issuers, listener metadata, physical states, thermostat targets and typed parent identity separate without hardcoding room/phrase-specific output.
