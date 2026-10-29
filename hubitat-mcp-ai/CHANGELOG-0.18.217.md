# Hubitat MCP AI v0.18.217 — General target relevance and collective device identities

## Live 29 October 2026 V2 comparison

The **second** v0.18.216 test attempted to investigate a subject identified by the model's read-only name lookup as `bathroom lights`; the complete original question was **not included** in the exported investigation details. That lookup returned `not_found`. A `hub_list_rooms` result reported 25 rooms but the native projection did not preserve its room records, and an unscoped `hub_list_devices` call timed out after **20,003ms**, followed by a rejected duplicate proposal. An unfiltered `hub_get_logs` returned 100 INFO rows and no WARN/ERROR coverage. A `hub_get_device_health` call returned 51 stale and one unknown-activity device. Without any verified bathroom light device state, V2 presented those unrelated stale-device observations as though they answered the question. Total run: 34.380 seconds; 3 successful reads of 4 attempted, no writes.

The first contemporaneous broader health investigation was different: eight of eight successful reads in 33.354 seconds, cross-source incident cases retained, and a model-authored in-loop proposal rejected with `invalid_findings`. This release addresses the **general subject relevance and unresolved multi-device identity** failure of the second run, not that separate narrative-format problem.

## Generic architecture correction

- The existing model-selected `homebrain_find_device` tool now supports **bounded collective name candidates** for source-attested device labels with a common leading token sequence and a conservative singular/plural variant (e.g., a collective name may match separately named instances). It does not guess device IDs, assert group membership, infer room capabilities, or automatically read/actuate devices. A large or broad group is not returned as a silently truncated verified set.
- Candidate device IDs are allowed only as independently provided, live source identities for subsequent **model-chosen, separately authorised READs**. The user-facing model is explicitly told that matching a source name is not proof of group membership, and that it must read actual states rather than use an unbounded full-hub listing.
- Add a **generic requested-subject evidence guard** that applies after the model has explicitly attempted name resolution (not by keyword-matching the original question). If that lookup remained unresolved, or a candidate set was only partially read, independently verified generic hub errors, health reports and logs remain in the full technical report but cannot replace an answer about the actual requested subject. The brief response instead clearly states the missing subject evidence, possible match coverage and any full-list timeout. A complete matching target READ set and normal broad hub questions continue through existing evidence validation.
- Add per-response `subject_relevance` diagnostics and an explicit `concise_answer_source=unresolved_named_subject_evidence` when source coverage is insufficient.

## Safety and scope

This is an experimental V2 READ-only change. It does **not** alter production Main Ask, authorised write operations, Hubitat rules or devices. It does not infer the actual original wording of the exported second test. A name group remains a set of candidates until separately verified by source reads; duplicate names and ambiguous identities are not silently chosen. No claim of general model parity with V1 or Claude follows from test coverage.
