# Native Rule Machine authoring: evidence/readiness boundary (2026-11-02)

**Status:** offline structural foundation only. **Native creation is NOT supported.** This is part of the permanent [Answer Quality roadmap](ANSWER-QUALITY-CHARTER.md), not a new project direction.

## Source-derived contract

Reviewed current upstream `kingpanther13/Hubitat-local-MCP-server` `libraries/mcp-native-documents-lib.groovy` (`toolSetRule`, `_ndOperationSchema`, `_ndValidateChange`, `toolCreateRuleDocument`, `_ndGuide`). The server accepts top-level `operation`, `rule_id`, `args`, `confirm`, `bestPracticeKey`. Create is `operation="create", args={parent_id,name,changes:[{part,value},...]}, confirm=true`. The parent **must** be native Hubitat `Rule Machine`. Trigger fields must use typed native `#`-indexed names; actions require type, subtype and typed native fields. It verifies native state and health after applying changes, but **can leave a partial active child on failure**.

The guide documents shape only: it does **not** supply authoritative native field names, selector values and timing semantics for an arbitrary `Certain Time` trigger and `off()` device action. The older `addTrigger/addAction` shortcut is not interchangeable. A native Rule Machine form **open** is explicitly potentially mutating and cannot be treated as a harmless schema probe. Neither an unconfirmed create operation schema nor a sample `getLogMsg` action proves this scheduling combination.

## What this PR delivers

`scripts/native_rule_document_preflight.py` is a **pure offline shape checker** built from the upstream native validators. It separately reports installed guide family, trustworthy unconfirmed-create schema shape, exact native parent identity, and one atomic trigger/action batch with typed `#` fields. It deliberately keeps `write_ready=False` even if all four checks pass. Synthetic regression tests check missing/malformed metadata, wrong parent identity, selector-field collisions, duplicate fields, incomplete/change-order batches, and absence of writes. This code is **not connected to the confirmation pipeline**. Existing v0.18.362 native-write refusal remains active.

The schema and sample changes in unit tests are synthetic fixtures; they **do not attest** native time/command field names or a working native scheduled rule. Passing these tests is a safety/shape result only, not an answer-quality benchmark or a successful rule creation.

## Preconditions before enabling native writes

1. Using **read-only installed-server evidence**, resolve the exact native Rule Machine parent ID and obtain the actual unconfirmed `hub_set_rule(operation="create",confirm=false)` schema. Do not assume upstream `main` equals installed gateway.
2. Establish exact capability-specific trigger and action native types, field names and values from authoritative nonmutating sources or safely isolated offline upstream tests. Do not use form `open` on the user's live hub merely for discovery. Verify calendar-date one-time semantics and self-disable behavior, including timezone/DST.
3. Extend the compiler only for fully attested typed combinations; preserve actual device identity/command checks, fresh duplicate list, confirmation replay contract recheck, backup, atomic batch, failure reconciliation and source-typed post-create readback. Do not create empty/active shells to populate later.
4. Prove negative tests and CI all green; then require **fresh explicit user approval** for any live creation. Check whether the previous 2026-11-02 15:35 rule exists first; never reuse its expired confirmation.

## Quality measurement

No new model calls, provider rounds, live operations, altered answers or latency changes in this PR. **Grounding / first-attempt quality / matched latency / Claude comparison: NOT MEASURED**. Continue same-packet evidence reviews under the charter; do not interpret structural CI as an answer-quality gain.
