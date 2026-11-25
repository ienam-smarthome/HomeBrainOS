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
