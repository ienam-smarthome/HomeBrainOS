# V2 deterministic receipt computation (homebrain_compute_receipt)

**Status:** code candidate, packaged as V2 `2.0.0-alpha.156`; not installed or accepted. PR #1744 first merged it under the alpha.155 label; the follow-up bump corrects that provenance. The alpha155 sealed pack covers exactly the memory/battery/gap cases this tool targets, so it must not be reused for alpha.156.

## Problem
Post-alpha154 source review found final answers whose facts were present in
successful receipts but mis-computed by the model: a battery range counted as
5/174 instead of 6/169, a 36,074.5 KB mean-to-latest difference reported as
~36 KB, and adjacent-row gaps with reversed timestamps. Each was being fixed by
a separate host-side projection module.

## Change
A reserved local, read-only tool lets the MODEL ask the client to count, filter
(`eq/ne/lt/lte/gt/gte/contains/exists/missing`), `unique_count`, `group_count`,
`min/max/mean/sum`, `sort`, `time_gaps` and `diff` over rows already returned by
an earlier successful native read in the same request. It reads no hub data,
parses no prompt, selects no device, and cannot write.

Safeguards: truncated receipts are refused; failed/local receipts are refused
with a list of usable receipts; output states rows in list, after filter,
missing field and non-numeric counts; timestamps must be ISO with offset (naive
and epoch values are not guessed); every result carries
`covers_only_rows_the_source_returned` and gap results state they are not proof
of absent events. Catalog name collisions are rejected like the clock tool.

Classified read-only (`is_read_only_review_tool`), excluded from source-progress
observations and from current-read evidence checks.

## Not claimed
This improves arithmetic fidelity only. It does not repair source selection,
continuity, causal attribution or model role selection. Measure on a new sealed
prospective cohort before any quality claim; bump the V2 alpha version when
packaging so acceptance provenance stays exact.

Tests: `hubitat-mcp-ai-v2/tests/test_receipt_compute.py`; full V2 suite 871 passed.


## Live alpha.156 review (24 November 2026, nemotron-3-super via cloud)

Three owner-run read-only first answers, verified against the original receipts
(raw captures stay private):

| Question | Answer | Receipt truth | Compute tool used |
| --- | --- | --- | --- |
| Battery 80-94 inclusive / none | 14 / 158 | 8 / 151 of 181 (list complete: count=total=181) | No |
| 80-min free-memory avg/min/max/latest delta | all correct (945,916 / 851,264 / 1,004,892 KB; 16,880 KB) | same | No (not needed) |
| Three biggest gaps, last 10 events | third gap 76.0 s, skipping a row | 65.454 s | No |

Findings: the tool was available (46 offered) but never chosen; the model
counted nested `currentStates.battery` values wrongly and paired non-adjacent
events. The memory answer also labelled a divide-by-1,024 figure as MB (16.48;
decimal is 16.88). Running the tool on the real receipts gives 8, 151 and
975.795 / 400.928 / 65.454 s, so the tool is correct and the gap is discovery.

## Alpha.157 change

Native results holding >=10 row objects gain `client_row_compute_hint`: true
receipt index, list path, real (including one-level nested) field names, and an
instruction to use the tool. It is derived from result SHAPE only, never from
the user's wording. Prompt now requires decimal MB. Still unmeasured: re-run the
same three questions on alpha.157 and check that the tool is called and exact.

## Live alpha.157 review and alpha.158 change

Re-ask of the battery question on alpha.157: the model made three native reads
(one rejected `detailed`+`attributeNames` call, then two `summary` pages of 100
and 81 of 181 devices). The new `client_row_compute_hint` reached it on both
pages with correct paths and fields, but the run ended in an Ollama Cloud model
timeout after ~134 s with no answer and no compute call. Two real defects:

1. The tool computed over ONE receipt, but a 181-device inventory is returned as
   pages (100 + 81), so a single-page computation would undercount.
   Alpha.158 adds `receipt_indexes` (2-12 pages), counting duplicate ids once and
   reporting per-page rows and duplicates removed. On the real capture, receipts
   [2, 3] give 8 devices in 80-94 and 151 with no battery, with 181 rows.
2. The model timeout is a provider/transport failure, not a runtime defect; it
   shows the model-led loop has no fallback when the model stalls after the data
   is already retrieved. Not changed here.

Still unmeasured: whether the model calls the tool at all when it does answer.

## Live alpha.158 review and alpha.159 change

On the user's hub, alpha.158 battery run 1 called the compute tool twice and gave
7 in range, 151 without a battery value, 181 rows (matches the receipt). A rerun
of the same question made one `hub_list_devices` read (all 181 rows), ignored the
hint and answered 7 and 155; the receipt gives 7 and 151, so the second figure was
wrong by mental arithmetic. A third capture (memory + front-door gaps) computed
all nine gaps correctly by hand but again made no compute call, mislabelled the
16:28:12 event as motion-active (it is inactive), and stated that no per-device
memory attribute exists after reading only 20 of 181 devices.

Change: when a result holds a large list of rows, the model answers, and no compute
call has run, the loop sends ONE internal message asking it to recompute any figure
over those rows with the tool or return the draft unchanged. The trigger is the
shape of the source and the loop state, never the wording of the question.
Switch: `enable_compute_nudge` (default on). Unmeasured: how often this changes
answers and its round-time cost.

## alpha.160

- UI: removed the AI Evaluation tab and Acceptance study link (backend routes `/api/evaluation/replay` and the acceptance router remain, unreachable from the UI).
- Prompt: source fields keep their own names (a runtime `total` is not memory); unavailable quantities are stated as unavailable; mixed event names are reported as a mix.
- `time_gaps` now also returns `gaps_in_time_order` (up to 50 gaps) beside `largest_gaps`.

## alpha.160 review and alpha.161

- Front-door gaps (alpha.160): all 9 gaps match the compute receipt, in order; the largest (75.888 s) is correct. Residual: the answer speculates about a "labeling mismatch" although the device is a contact sensor whose returned events are all `motion` reported via the SwitchBot hub.
- Memory (alpha.160): `hub_get_logs` devices rows carry `pct` (share of device runtime) and `total` (runtime ms). The answer called `pct` a share of hub memory. The prompt rule alone did not prevent it.
- Battery (alpha.160): the model repeated an identical `limit: 200` read, generated ~5,000 tokens without computing, then timed out.
- alpha.161: `client_field_meaning` note on `hub_get_logs` runtime tables (gated on tool name and returned field names); identical successful read-only calls in one request are refused with a pointer to the earlier receipt; `_find_rows` searches deeper so nested log rows get the compute hint.

## alpha.161 review and alpha.162

- Battery (alpha.161): 6 devices in 80-94 and 151 with no battery value, list complete (181 of 181, `hasMore=false`); an independent recount of the receipt matches. Residual: the answer adds an unneeded claim that lexical and numeric comparison agree.
- Memory window (alpha.161): figures were right, but the answer said they were computed with the compute tool on the 16-entry window when the tool was run over the wrong list (a client-added `returned_samples` list) and could not filter by time. It also gave MiB when MB was asked.
- alpha.162: `_find_rows` skips `client_*` keys; lt/lte/gt/gte compare `MM-DD HH:MM:SS` stamps as text within one calendar year; fields ending in `KB` get `unit_conversions_from_KB` (decimal MB and MiB) for result/min/max.
- Not done: no guard yet for an answer that claims compute-tool provenance without a matching `local_compute` receipt.

## alpha.162 review and alpha.163

- Memory (alpha.162): answer used `stateSize` (bytes of stored state) as a labelled proxy and gave a correct decimal free-memory figure, but ranked only the 50 rows returned of 293 (`total: 293`, `nextCursor: "50"`) without saying the ranking was partial. Two paging retries failed (a list-valued `mode` with a cursor; then `cursor 50` reported out of range, cause not established).
- alpha.163: `client_row_compute_hint.coverage` (rows returned, source-reported total, next cursor, `partial`) derived from the result's own `total`/`matched`/`nextCursor` fields, never from user wording; compute adds `unit_conversions_from_bytes` for `stateSize` and `*Bytes` fields.
- Not done: no enforcement that the final answer states partial coverage; the odd `size=20` cursor error is uninvestigated.

## alpha.163 review and alpha.164

- Memory (alpha.163): `hub_get_logs` was read with `mode: apps`, so the answer ranked apps (largest `stateSize`: Device Health Monitor, 1,072,890 bytes) while the question asked about devices. The coverage note said partial (50 of 189) but the answer did not. The "other notable" list skipped Google Calendar Notifier (76,456), Automation Map (61,214) and 08. Octopus Energy (58,723) in favour of smaller entries, and was not in computed order.
- alpha.164: `partial_coverage_note` appends a structural footnote ("N of M rows") when a successful compute receipt used a source receipt whose recorded `row_coverage.partial` is true; prompt rule for partial coverage, ranked completeness and apps-vs-devices; mobile composer wraps buttons under the input; `GET /api/network/status` (UI header required) runs one bounded probe set (TCP to 1.1.1.1:443 and 8.8.8.8:53, DNS lookup, the configured Hubitat host, optional `network_router_host` by ping then TCP) on button press only.
- Not done: the footnote is not verified end to end against a live run; nothing forces the model to read the devices table for a devices question; the add-on cannot see the hub's own internet access (a Hubitat Hub Ping device or Rule Machine ping can).

## alpha.164 review and alpha.165

- Memory (alpha.164): `hub_get_logs` devices, 50 of 293 rows. Top five by `stateSize` (79,818; 37,754; 33,333; 29,112; 23,642) match the receipt, and the appended coverage footnote and the model's own "50 of 293" were both correct. Faults: a column titled "Approx. Memory" for a state-size field, and bytes divided by 1,024 shown as KB. The 50 rows are the busiest by runtime, so the ranking is not hub-wide; the model did not page.
- Network card (alpha.164): without a router address all four checks were green; with one, Router showed "no response" under an "Internet reachable" headline. Cause not established (address form, ping unavailable, or no answer on 80/443/53/22).
- alpha.165: sorted rows over byte fields carry `client_<field>_KB_decimal`; field note forbids a Memory/RAM column title; router value accepts URL or host:port; ports probed in parallel; failed router row says what was tried; summary is a warning when only the router fails.
- Not done: paging past 50 rows (an earlier cursor call returned "out of range (size=20)", unexplained); no enforcement of column titles.

## alpha.165 review and alpha.166

- Network card (alpha.165): with the router address set, Router showed 24.9 ms and all five rows were green.
- Memory (alpha.165): receipts are `hub_get_metrics` (free memory 847,352 KB) and `hub_list_devices` limit 5 of 181. The answer gave no per-device memory (correct that none exists) but then tabulated event counts for five devices and said they were "obtained by running the event-lookup call for each ID". No `hub_list_device_events` call exists in the request, so those numbers are unsupported. It also said "you already have the list" although only 5 of 181 devices were read, did not use `hub_get_logs`, and the "Interpretation" and tuning advice rests on the invented counts. Only `lastActivity` markers (2026-11-25 01:33, 01:30, 01:36 for three devices; 2026-08-19 for the virtual switch) are real, and they are not event counts.
- alpha.166: `unrun_tool_note` appends "Not run in this request: ..." for catalog tool names the answer mentions with no successful receipt (compared with the declared catalog and receipts, not the question). Prompt rule added. End-to-end test covers this and the alpha.164 coverage footnote through the agent loop.
- Not done: the note only exposes an unbacked claim, it does not remove or correct the invented figures, and a fabrication that names no tool is not caught. Run-to-run variation in which source the model reads (logs table vs inventory) remains.

## alpha.166 review and alpha.167

- Memory (alpha.166): page 2 of devices (cursor 50, mode as a string) was read successfully, but the sort ran over page 1 only (receipt 2). Page 2's largest `stateSize` (Lewisham 18,953) is below the fifth-ranked value (23,711), so the top five stand over 100 rows. Values (79,818; 37,754; 33,333; 29,030; 23,711), free memory 881,592 KB, 43 C, 172 MB and 11 h 55 m match the receipts. Faults: 861 MB is KB/1,024; the coverage footnote says 50 of 293 although 100 rows were read (it reflects the computed receipt only); the "Not run" note correctly flagged a suggested hub_get_memory_history.
- alpha.167: `unit_conversion_note` attaches `client_unit_conversions` (decimal MB, MiB) to results with `*KB` fields. UI declutter: helper paragraphs and privacy text moved behind ⓘ toggles (text kept), System Health attention banner built from the rendered attention cards, `.needs-review` cards ordered first with larger amber counts, network card border by result level, chart options collapsed (the browser smoke test now opens them).
- CI lesson: `browser_smoke.py`, `test_ui.mjs` and `run_v2_golden_suite.py` run in CI but not in the pytest suites; run them before pushing UI changes. The first push hid text the smoke test reads (`#healthCoverage`, `#healthSnapshotNotes`) and the layout select; those stay visible or the test opens the details.
- Not done: the sort was not combined across pages (receipt_indexes); no value-based highlighting on Hub Diagnostics tiles; Ask-tab answer summary line is still long.

## alpha.167 phone review and alpha.168

- UI review of six alpha.167 phone screenshots found: timeline chart clipped on mobile (scrolls sideways at 860 px; titles cut off, no cue), two status dots, "2339h" instead of days, "1 minutes", a selected-point box printing raw field names, ⓘ buttons on their own rows, duplicated snapshot phrases, a header and tabs filling about a third of the screen, blue (not amber) attention borders, centred network labels.
- alpha.168: UI only. Header compact on mobile with sticky tabs; one status dot; inline ⓘ; a swipe hint on the chart (chart titles keep their "independent scale" and "not utilisation" wording, which tests protect); `#timelineReadoutShort` headline with the full text kept in `#timelineReadout` inside "Source details" (open on wide screens); one-line snapshot status; days for 72 h or more; amber attention borders; left-aligned network rows; keyboard hint cleared on touch devices.
- Not done: the chart still scrolls sideways on narrow screens rather than rescaling; Hub Diagnostics tiles have no value-based highlighting; the 15-minute memory sawtooth and the 97-day heartbeat inactivity are observations to investigate, not explained.

## alpha.169: Ask-tab tightening, README archive, question-text ratchet

- Phone Ask tab: New chat sits inline with the heading, the subtitle is hidden below 650 px, the empty state is one line and the composer row is shorter.
- The per-alpha history moved from `hubitat-mcp-ai-v2/README.md` to `docs/HOMEBRAIN-V2-ALPHA-HISTORY.md`.
- `tests/test_question_text_gating_ratchet.py` counts regex calls whose argument is user question text (81 at baseline across 13 modules). It fails if any module grows or a new one appears, and fails if a count drops without lowering the baseline. No agent behaviour change.

## alpha.170: paging safeguards and phone chart fixes

- `unissued_cursor_error`: a `cursor` argument must equal a `nextCursor` returned by an earlier successful call to the same tool in this request (structural, from receipts). Otherwise the call is not sent; the model gets a recoverable error and the receipt records `hub_called: false`.
- Compute results list `same_source_receipts_not_included` (same tool and arguments apart from cursor/offset/page). The footnote reports it, sums rows across combined pages, and names the source table. No question or answer wording is read.
- UI: timeline chart min-width 860 -> 640 px on phones, shorter CPU title, overlap-skipping time-axis labels on both charts, clean Ask empty state, one-row Troubleshooting cards.

## alpha.171: cursor continuation and automatic network status

- Evidence (alpha.170 capture, private): the first `hub_get_logs` read (`mode:["devices"]`, `limit:0`) returned 50 of 293 rows and `nextCursor:"50"`. Cursor reads then failed three ways: list mode with a cursor ("cursor pages one mode"), and single mode without `limit` ("cursor 50 is out of range (size=20)", the default page size of 20). No call used single mode with `limit:0` and the cursor.
- `cursor_continuation` (receipt_compute.py): a cursor read is sent with the issuing receipt's arguments (single-item mode list becomes a string), an empty cursor is removed, and a cursor the request never received is refused locally. The model gets `client_cursor_note` naming the receipt and the changed arguments. Structural, from receipts only.
- Footnote: failed paging attempts are reported ("Paging: N attempt(s)...") and the source mode prints as text, not a Python list.
- UI: network status runs when System Health opens and every 60 s while that tab and the page are visible. Check network still runs it now.
- Not verified on a live hub: that the hub accepts `mode:"devices", limit:0, cursor:"50"`.

## alpha.172

- Evidence (alpha.171 capture, private): a `sortBy:"stateSize"` read returned rows already in descending order, yet the answer called them a partial snapshot where larger entries might exist, and the footnote said the remaining rows were not read.
- `rows_hint(result, index, args)` now adds `coverage.ordered_by_source` when the call named a sort argument and the returned numeric field is monotone; the footnote then reads "already ordered descending by its own `<field>` sort" and says sort-before-paging was not independently verified. Structural only (arguments and returned values), no user-text matching.
- Prompt: prefer the tool's own sort/limit parameters for rankings; describe source-ordered rows as leading rows of the hub's ordering.
- UI/status: model phase shows "AI model round N · M step(s) done"; tool phase shows "Waiting on <tool>".
- Not verified live: whether the hub always sorts before paging.

## alpha.173

- UI only: `has-reported` class on System Health snapshot tiles with state readings and a count above zero (outside Needs attention) colours the number with `--hb-accent`.
- UI only: `is-offline` class turns the Reported offline count and left edge red when the count is above zero with state readings.

## alpha.174

- UI only: light-theme overrides for System Health banner, network card, attention/offline/reported count colours; Currently reported counts are green in both themes.
- alpha.173 capture (private): sortBy read of 20 rows plus compute; footnote used the new source-ordered wording; answer still called stateSize a proxy that 'correlates with memory consumption' (unsupported); the prompt rule on not equating stateSize with memory needs tightening (not in this alpha).

## alpha.175

- `field_meaning_prose_note(answer, receipts)` (receipt_compute.py), appended beside the coverage note. Trigger is structural (a receipt recorded `field_meaning_fields`); it inspects the model's answer clauses, not the question. Heuristic: clause contains memory/RAM and `stateSize` with no negation word.
- Limits: a heuristic on model wording; may miss paraphrases or flag a correct clause lacking a negation word.
