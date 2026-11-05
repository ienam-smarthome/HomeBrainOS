# HomeBrainOS 0.18.416 — native date-trigger read diagnostics and bounded pagination

## Installed 0.18.415 observation (5 November 2026, 15:47 UTC)

The requested read-only exact-ID retry now correctly routes through `unified-mcp-agent`, domain `native_dated_trigger_discovery` (routing acceptance passed). The 42 visible native Rule-5.1 children were inventoried in 263ms. Two safe `hub_set_rule(operation=read,rule_id=2967/3985,args:{sections:[triggers,settings]})` calls ran for **214ms** and **240ms** respectively. Both returned `readVerified=false`; total UI latency approximately **0.8s**, no model rounds, four evidence receipts (inventory, two native documents, local projection), no modifying calls. No date-specific trigger was proven. The returned receipts could not distinguish an upstream MCP error from a successful but malformed/incomplete document, because the scanner reduced both to `Native trigger/settings read unavailable or incomplete` and discarded all non-sensitive diagnostic context.

## Upstream read contract

Upstream `libraries/mcp-native-documents-lib.groovy` documents `hub_set_rule(operation=read)` as read-only, without opening editor forms. A native document can be paged by requesting exactly **one section** using `args:{sections:["settings"],cursor:"",limit:50}` (or `sections:["triggers"]`), following a numeric `nextCursor`; page metadata exposes `offset`, `total` and `revision`. Source code enforces the server response-size budget and may shrink a returned page. The existing whole-document read could exceed that budget on large native rules, but this is a **hypothesis**, not yet a verified explanation for IDs 2967 or 3985.

## Changes

- Record a fixed, non-sensitive `unpagedFailureCode` in each per-ID source read diagnostic; distinguish a native source rejection, response-size suspicion, unexpected shape, missing sections, identity mismatch and complete typed read. Never expose raw source errors or private setting values.
- Only when a **user explicitly selects native rule IDs** and the unpaged source did not return a complete typed document, attempt read-only paged fallback through the same independently classified native read operation. All requested IDs must first match the visible built-in native child-app inventory; never issue a direct read for a missing or guessed ID.
- Read at most **3 trigger pages** and **8 settings pages per exact rule ID**, 50 rows/request, with hard totals of 100 triggers / 400 settings. Require exact `rule_id` on every page, valid `page.offset`/`total`/`revision`, revision and total stability across pages, strictly advancing cursors, no duplicate settings and complete requested sections. Reject malformed pages, changed revisions, response limits and source errors; never interpret incomplete data as an absent dated trigger.
- Reconstruct a complete document **only after** both sections finish; then apply the existing allowlist for indexed `time#`, `atTime#`, `date#`, `atDate#` fields and validated date enablement. The final evidence contains only allowlisted observations and safe failure codes, not unrelated settings or raw trigger/action content.
- Treat a multi-ID retry as a request to inspect **all** listed IDs even if one positive date-enabled trigger is found. Ordinary offset-based inventory scans remain unchanged and incur **no new pagination calls**.
- Preserve `readinessForMutation=false`, the native authoring >=5.1.6 gate, all confirmation and backup requirements, and no native forms or writes.

## Verification and next acceptance

Regression tests replay a server-sized-error whole-document read with two complete paged sections (including multi-page settings) and verify both IDs independently, revision mismatch rejection, invalid cursor, wrong rule ID, excessive page total, private-value redaction, unchanged offset scans and no fallback after a successful unpaged read. All source requests are classified `read`.

**After installation of v0.18.416**, repeat exact native rule IDs **2967 and 3985**, explicitly read-only. Inspect `readDiagnostics` in the `typed_native_dated_trigger_discovery` receipt: `unpagedFailureCode`, `pagedAttempted`, `pagedOutcome`, `pagedSectionsRead`, each `readVerified`, and any allowlisted date-field groups. A successful paged native read does not prove a dated trigger exists or that its one-shot execution works. If paged reads also fail, use the safe failure codes to identify the next specific upstream source-contract issue rather than guessing.

Live installed acceptance and whether pagination resolves either real rule remain unverified.
