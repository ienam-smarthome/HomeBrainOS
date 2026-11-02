# Native Rule Machine authoring: evidence/readiness boundary (2026-11-02)

**Status:** offline structural foundation only. **Native creation is NOT supported.** This is part of the permanent [Answer Quality roadmap](ANSWER-QUALITY-CHARTER.md), not a new project direction.

## Source-derived contract

Reviewed current upstream `kingpanther13/Hubitat-local-MCP-server` `libraries/mcp-native-documents-lib.groovy` (`toolSetRule`, `_ndOperationSchema`, `_ndValidateChange`, `toolCreateRuleDocument`, `_ndGuide`). The server accepts top-level `operation`, `rule_id`, `args`, `confirm`, `bestPracticeKey`. Create is `operation="create", args={parent_id,name,changes:[{part,value},...]}, confirm=true`. The parent **must** be native Hubitat `Rule Machine`. Trigger fields must use typed native `#`-indexed names; actions require type, subtype and typed native fields. It verifies native state and health after applying changes, but **can leave a partial active child on failure**.

The guide documents shape only: it does **not** supply authoritative native field names, selector values and timing semantics for an arbitrary `Certain Time` trigger and `off()` device action. The older `addTrigger/addAction` shortcut is not interchangeable. A native Rule Machine form **open** is explicitly potentially mutating and cannot be treated as a harmless schema probe. Neither an unconfirmed create operation schema nor a sample `getLogMsg` action proves this scheduling combination.

## What this PR delivers

`scripts/native_rule_document_preflight.py` is a **pure offline shape checker** built from the upstream native validators. It separately reports installed guide family, trustworthy unconfirmed-create schema shape, exact native parent identity, and one atomic trigger/action batch with typed `#` fields. It deliberately keeps `write_ready=False` even if all four checks pass. Synthetic regression tests check missing/malformed metadata, wrong parent identity, selector-field collisions, duplicate fields, incomplete/change-order batches, and absence of writes. This code is **not connected to the confirmation pipeline**. Existing v0.18.362 native-write refusal remains active.

The schema and sample changes in unit tests are synthetic fixtures; they **do not attest** native time/command field names or a working native scheduled rule. Passing these tests is a safety/shape result only, not an answer-quality benchmark or a successful rule creation.

## Live read-only follow-up — reported field sample vs actual provenance (2026-11-02)

The user supplied a v0.18.363 HomeBrain read-only investigation for candidate native rule **4136**, reported label `Internet: CAM OFF @10pm`. The model's answer reported `tCapab1="Certain Time (and optional date)"`, `time1="A specific time"`, `atTime1="22:00"`, action `actType.1="switchActs"`, `actSubType.1="getOnOffSwitch"`, `onOffSwitch.1=["6985","6988"]` and `onOff.1=false`. This is a **reported field candidate only**, not an authenticated native document read.

**Provenance mismatch:** The supplied complete Technical JSON contains exactly **five** tool receipts: `hub_list_apps`, `hub_list_rules`, `hub_search_tools`, and two `hub_get_app_config(appId=4136)` reads. It contains **no `hub_set_rule(operation="read")` receipt** despite the model claiming it used that operation. Those app-config tool receipts do not expose full typed trigger/action values in the exported summaries, so this source packet cannot independently prove the native field values. The model also inferred parent ID **169** from matching aggregate counts (41 children/rules) rather than a returned child `parentAppId`; this is not proof of parentage. The `date1` field was empty in an apparently **daily** example; no dated **one-time** trigger, self-disable, DST or post-execution lifecycle was verified.

**Next nonmutating evidence needed:** A genuine read-only `hub_set_rule(operation="read", rule_id=4136)` receipt/structured response with typed fields and child parent identity, plus a safe existing *one-time dated* rule sample, or equivalent authoritative upstream offline test evidence. Never infer typed values solely from model prose or summary keys. Do not call `operation="form"`, which upstream warns can mutate, solely to discover fields. No native authoring write is enabled.

## Verified native document read recovered in v0.18.364 (2026-11-02)

A subsequent user-supplied complete Technical JSON **does** include a successful, source-linked `hub_manage_native_rules_and_apps(tool="hub_set_rule",args={operation:"read",rule_id:<rule>,confirm:true})` receipt. Its non-form document result showed the native 22:00 trigger and Switch OFF typed settings. This supersedes the prior **unverified model-only read claim** for those overlapping fields. The action method `getOnOffSwitch` was in the returned action row; its settings include `actType.1=switchActs`, but not a separate `actSubType.1` setting in that extracted row. Do not invent the missing setting. The `onOff.1` string `"false"` is a stored OFF flag; the switch selection is verified as a multiple `capability.switch` row. `uiChecked=false` means the native form/editor was **not** inspected.

The gateway's READ operation is **not a write** according to upstream source, even if it carries `confirm:true`; HomeBrain's v0.18.364 effect classifier nevertheless tagged it `mutates=true` and queued an unnecessary sensitive action confirmation. Correct that local permission/evidence contract before further authoring. **Still unproven:** direct parent-child link, future dated one-time time-trigger field contract, timezone/DST and run-once/self-disable. A daily 22:00 sample alone is not an authoritative one-time rule compiler contract. Native creation stays disabled.

## Preconditions before enabling native writes

1. Using **read-only installed-server evidence**, resolve the exact native Rule Machine parent ID and obtain the actual unconfirmed `hub_set_rule(operation="create",confirm=false)` schema. Do not assume upstream `main` equals installed gateway.
2. Establish exact capability-specific trigger and action native types, field names and values from authoritative nonmutating sources or safely isolated offline upstream tests. Do not use form `open` on the user's live hub merely for discovery. Verify calendar-date one-time semantics and self-disable behavior, including timezone/DST.
3. Extend the compiler only for fully attested typed combinations; preserve actual device identity/command checks, fresh duplicate list, confirmation replay contract recheck, backup, atomic batch, failure reconciliation and source-typed post-create readback. Do not create empty/active shells to populate later.
4. Prove negative tests and CI all green; then require **fresh explicit user approval** for any live creation. Check whether the previous 2026-11-02 15:35 rule exists first; never reuse its expired confirmation.

## Quality measurement

No new model calls, provider rounds, live operations, altered answers or latency changes in this PR. **Grounding / first-attempt quality / matched latency / Claude comparison: NOT MEASURED**. Continue same-packet evidence reviews under the charter; do not interpret structural CI as an answer-quality gain.
