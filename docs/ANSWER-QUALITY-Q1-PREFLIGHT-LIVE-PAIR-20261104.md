# Q1 live pair review: read-only evidence recovery (2026-11-04)

## Scope and sample identity

Two user-supplied real HomeBrain API response envelopes, installed add-on
**0.18.389** then **0.18.390**. Both used **Ollama Cloud Free Gemma 4 31B**.
Both API envelopes state `request_class=live-read` and share exactly the
same normalized API question hash. Neither attests actual model-delivered
prompt, first-attempt status or deployed Git SHA; all three provenance flags
are `false` in both responses. This is **one same-API-prompt
before/after diagnostic pair**, not a formal source-graded frozen-case
accuracy score or proof of Claude parity. No private tool arguments,
household labels, device IDs, raw answers or source inventory content are
stored in this review.

The separately merged v0.18.390 change [PR #1381](https://github.com/ienam-smarthome/HomeBrainOS/pull/1381)
is a plausible explanation for the change in tool-selection behavior,
because the candidate receipt reports
`read_only_write_recovery_view=1`. A before/after pair is **not** a
controlled causal isolation of every latency or model-quality change.

## Observed counters, not inferred accuracy

| API technical metric | v0.18.389 | v0.18.390 | Observation |
| --- | ---: | ---: | --- |
| Total duration | 25,925 ms | 15,168 ms | -10,757 ms, 41.5% reduction (single sample) |
| Cloud provider processing | 23,042 ms | 11,238 ms | -11,804 ms |
| Model rounds | 5 | 4 | -1 |
| `tool_calls` | 2 | 7 | +5 |
| Successful read receipts | 2 | 7 | +5; different sources/coverage, not proof of correctness |
| Blocked unauthorized-write model batches | 2 | 1 | -1; still one unnecessary model proposal |
| Read-only recovery view | 0 (absent) | 1 | General v0.18.390 recovery triggered |
| Transport `success` | true | true | Only confirms API response |
| Request outcome | success | unresolved | Candidate did not imply verified overall resolution |
| Recorded control writes | 0 | 0 | No mutation is shown in either supplied receipt |

The release target for routine reads is under 15s; candidate's measured
**15.168s** is still just above that threshold. A single observation cannot
establish median, p95, reproducible first-attempt gain or source-backed
answer accuracy. The seven receipt rows include a tool search and a local
resolution attempt, not seven independent proofs of the six user objectives.

## Manual source-to-claim review — neither fully established nor scored as pass

- **Hub clock:** The candidate answer explicitly says it *derived* hub
  clock from an anchor and timezone. No independent hub-clock readout is
  captured in the public source-receipt metadata.
- **Backup freshness:** A successful scoped `hub_list_backups` read is
  recorded, but the model reports the latest as an early-November-3
  timestamp even though an earlier installed v0.18.388 source projection
  had reported a newer late-November-3 hub-local backup. Different-time
  inventories and a model-selected value must be reconciled against actual
  source records before certifying the newest or suitably fresh backup.
- **MCP Rule Server version:** The current answer attributes `5.1.5`
  to `hub_get_info`, whose receipt lists Hubitat firmware and hub
  hardware fields, not MCP `initialize.serverInfo.version`. The
  earlier v0.18.388 independent *serverInfo* version 5.1.5 is useful
  historical evidence; it is not a fresh proof of the current answer's
  claimed source.
- **Direct virtual-device tool:** `hub_search_tools` ran with a
  capability-name query, but discovery receipt summary alone does not
  include the matched server schema or independent permission/availability
  details needed to prove actual direct invocation readiness. This is
  not authorization to create a device.
- **Disposable switch absence:** The model searched a generic label,
  not the previously specified unique test-switch label. Zero
  *targeted candidates* for the searched phrase is not a globally
  scoped absence proof.
- **Dated Rule Machine absence:** An all-rules listing was returned,
  but the answer cites a search for `dated` in labels. A native one-time
  rule can have a different canonical suffix. A failed substring match
  does not prove no qualifying scheduled rule exists.

**Verdict:** More requested source families were actually attempted;
independent factual support for the six model-published conclusions is
incomplete. A read receipt's success is not the same as the value,
scope or temporal coverage needed for a claim. Do not use this outcome
to enable a production blocker or authorize a native timed test.

## Reproducible metadata-only comparison

Use `scripts/answer_quality_live_receipt_diff.py` with locally
retained, unredacted technical JSON envelopes (never commit them).
The tool checks identical API-boundary prompt digest, same model and
live-read class; reports only safe counters, deltas, provenance gaps and
`not_measured` answer-quality fields. It does not scrape or quote the
model's response, issue hub calls, validate device values, or infer
the cause of latency improvements. Synthetic tests cover divergent
question hashes, missing values, misleading transport successes,
untrusted identifiers and write-receipt detection.

## Next roadmap step

Q1: assess a distinct ordinary read-only multi-device question using the
fixed baseline task inventory and exact first response plus technical
JSON, with human source review of actual value/scope evidence.
Do not recycle the same Internet-blocker incident as a new benchmark
unconditionally. Then proceed to Q2 identical-packet model A/B if
source evidence is complete enough. The formal reviewed denominators
and Claude comparison remain **NOT MEASURED**.
