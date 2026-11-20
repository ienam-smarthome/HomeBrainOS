# HomeBrainOS V2 alpha.154 — evidence chronology, scope and source resilience

**20 November 2026. Code candidate, not installed or promoted.**

## Original baseline

The intact, original source-real alpha153 ten-case capture had 5/10 advisory
useful complete first answers, four partial and one failed, with no established
formal atomic-claim grounding rate. All five native tool failures and nine
model rounds were in battery inventory case 02 (149.106 seconds). Case 08
misidentified a health status event as a dated physical measurement, asserted
an unreturned ON event and reversed command/status timestamps. Case 10 used a
native `modes.past` response while the offline report and fallback expected
direct `entries`. Case 01 included an out-of-window row in a 75-minute table.
None of these original source exports have been modified or retried.

## General interventions

**Original log envelope source adapter** —
`native_past_log_receipt.original_past_log_source` recognises both
`{mode:past, entries:[...]}` and `{modes:{past:{entries:[...]}}}`, provided
the original successful `hub_get_logs` receipt actually requested only past
mode. It does not rewrite the raw source, combine overlapping pages or infer
total count scope. Historical publication, source-only grouping, typed shadow
facts, model-facing anchors/ledger and the separate OFFLINE first-answer audit
all consume the same validated original past response. A categorical
interpretation of `total` as the number scanned for this query is blocked
from publication; the accepted fallback may display supported per-source
returned counts while explicitly withholding total semantics.

**Source event chronology check** —
`event_sequence_publication` uses only original, dated, same-device native
event rows to challenge an asserted intervening switch ON/OFF that has no
dated matching state report after an opposite command, reverse-order claims
about the newest command versus health status, or a `healthStatus` event
described as a dated measurement. It cannot certify arbitrary prose; absence
of a returned row never proves historical non-occurrence. On detected unsafe
publication, a bounded source-only report preserves original positive states
and commands with their actual chronological separation. Multi-device and
uninspectable target scopes remain outside this narrow enforcement floor.

**Detailed inventory read budget** —
`inventory_read_limits` denies a detailed page limit above 100 before
execution and denies further detailed requests after two source-failed
detailed inventory reads in the same Ask. It does not execute or select a
summary call, remove the native summary capability, or count a denied read
as actual source evidence. A failed detailed source result or timeout
supplies static guidance to the model about schema-supported summary /
attribute projections and distinct-ID pagination coverage. All native
writes, approvals and routine-action paths are unaffected.

**Exact memory sample UTC window** —
`memory_window_provenance` uses a successful original client-clock receipt
and original native memory-history rows to compute an exact requested
minute/hour cutoff. Source timestamps reported only as MM-DD local time
are interpreted using the configured hub timezone and client year; that
interpretation is disclosed and is not independent server time proof.
Original returned rows are discrete measurements, not continuous coverage.
A clearly out-of-window timestamp included as a table sample triggers an
output-only projection of in-window source samples. Unrelated prose is not
blindly rewritten. The model receives a compact source-derived boundary/
sample-count/gap index without a new native call.

## Safety, tests and limits

- No Hubitat writes, device control, automation changes, native read retries,
  model tool selection, or new forced AI model rounds were added.
- Original read-only permission preflight remains source-reported
  Read ON / Write OFF, with independent enforcement testing still outstanding.
- Fictional unit/integration tests check nested/direct past logs, non-past
  rejection, offline audit counters, original log grouping, total-scope
  publication rejection, dated event chronology, status-vs-measurement,
  actual subsequent switch event, and inventory resource ceilings.
- Valid original source facts are not fabricated; authoring new native claims
  from inferred physical effects remains prohibited.
- Alpha154 code CI is not installed empirical evidence or a promotion gate.

## Fresh prospective acceptance

`2.0.0-alpha.154` uses `alpha154-prospective-v1` and
`/data/homebrain-v2-alpha154-acceptance`. Previous alpha151/152/153
manifests and private captures remain frozen. After exact-head CI and
installation, use a genuine dedicated per-client token with Read ON / Write
OFF, seal the new pack with exact current app/device labels, capture each
first answer *once*, export ten original JSONs plus report, and independently
score against >=90% atomic grounded claims, >=80% useful complete answers,
zero unsupported definitive causes and zero native write/approval regression.
Never promote alpha154 from CI-only or claim the new mechanisms are
already empirically verified.

**Rollback:** restore the last merged alpha153 commit
`5b01d49da2942ce2865a70c461e447c30a3eb4cb`;
preserve private capture directories.
