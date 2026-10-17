# v0.18.22 — Reconstruct paginated driver source and verify runtime obligations

## Live regression (v0.18.21)

Source-led investigation of Bedroom 3 Mesh (7103, Groovy driver code ID 3686) read 20,531 source offset units in **six** `hub_get_source` calls (4000/4000/4000/4000/4000/531) and used DeepSeek Pro for all five rounds. The final answer made a substantially better method-level explanation but incorrectly stated that the chunks have no line numbers, did not retrieve current device state, events or logs, and still marked `objectiveSatisfied=true`.

## Architectural updates

- Introduce a request-local `SourceChunkCollector` that assembles actual returned driver source across separately paginated tool calls. Validate source ID, declared total, offset, source content, optional next offset and advertised chunk length. Accept consistently offset-contiguous Python-codepoint or Java UTF-16 spans; refuse gapped, overlapping, inconsistent, invalid or mixed-source chunks. Never persist raw Groovy beyond this live request.
- Once complete, re-use the existing bounded lexical method-body projector. Deliver method-level excerpts with **source-relative line numbers**, even if the user/model retrieved the source as six pages. No new MCP reads or device commands are needed for this projection.
- Keep complete source and actual device-runtime evidence as separate proof obligations. For a question explicitly asking source *plus* current/historical device behaviour, only scoped current state, device history and device logs for the **same** device satisfy runtime correlation.
- Missing runtime sources mark `objectiveSatisfied=false`, `questionResolved=false`, metric outcome unresolved, with `runtimeEvidence.checked/missing` and a clear explanation. Complete source still reports complete source coverage independently. Pure source-only questions do not require irrelevant device/log calls.

## Tests and scope

Reproduce six-page full Groovy source reads, out-of-order and repeated pages, gaps/overlap, conflicting code ID/total and invalid Unicode. Verify full method evidence projection only on contiguous reconstruction, and source-only vs mixed runtime coverage. No new device control permissions, paid-budget changes, billing changes, source execution or sensitive writes. All 3 CI workflows must pass; live validation after installing the add-on remains necessary.
