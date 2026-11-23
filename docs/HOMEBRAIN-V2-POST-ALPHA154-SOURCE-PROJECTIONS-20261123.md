# V2 post-alpha154 source-bound output candidate — 23 November 2026

**Candidate only; do not call this an installed or accepted alpha155 package.**

## Independent original-source intake

The owner supplied the *original* first-answer Technical JSON files for both frozen alpha153 and alpha154 ten-case private cohorts. Only redacted case IDs and mechanical summaries are included here; original labels, raw answers, source results, event messages, and model contents stay private.

Observed mechanical comparison (cohorts have **different case wording, source states and sampling times**, so do not treat these as a matched controlled model-quality experiment):

| Cohort | Captured | First responses marked success | Native attempts successful | Total rounds | Reported server median | Reported server maximum |
| --- | --- | --- | --- | --- | --- | --- |
| a153 | 10/10 | 10/10 | 25/30 | 40 | 17.919 s | 149.106 s |
| a154 | 10/10 | 9/10 | 21/21 | 35 | 18.230 s | 38.644 s |

These mechanical counts are NOT useful-answer, factual-grounding or causal-claim grades. In alpha154, successful native reads still produced source-evident wrong or omitted final facts.

### Specific alpha154 source-backed observations

- **a154-02:** the single returned native projected battery inventory covers offsets 0–199, reports 201 hub devices and hasMore=true. Exactly **6 unique returned IDs** have numeric battery values within requested 80–94 inclusive, **31** returned IDs have numeric batteries, and **169 of 200** returned IDs lack the battery attribute. The model said 5 and 174; it also correctly qualified the 201st unreturned device as unknown. No claim about that final device is justified.
- **a154-03:** two successful focused inventory receipts contained valid stored switch/level pairs, but model final was empty. The new source-only fallback can present the returned snapshots without inventing event timestamps or physical effects.
- **a154-10:** past-log queries returned 100 and 188 rows in overlapping query scopes, with matched counts 187 and 188 and separate source aggregates. The final answer omitted requested per-source counts. The existing grouping helper can publish source-grouped results from ONE validated original receipt, not sum the overlapping pages or reinterpret aggregate totals as a query-wide scan count.
- **a154-01:** requested 80-minute free-memory values had window mean **925122.5 KB** and latest sample **889048 KB**. The model described the difference as approximately **36 KB**, instead of **36074.5 KB**. Memory time-window classification was otherwise source indexed; do not generalise this to an independently proven memory trend.
- **a154-09:** answer said a no-event gap indicated the contact stayed closed, though the bounded event rows do not prove continuous coverage; some gap descriptions reversed timestamps. No categorical continuity is supported.
- **a154-05:** same-value idle reports had an exact 1181.156 s separation, but those two returned state rows alone do not establish the state trajectory between them.

Source/first-attempt attestation and independent enforcement testing are separate requirements. Detailed claim-level quality grading remains an open operator/reviewer step. No formal grounded-claim numerator or denominator is invented.

## Proposed bounded original-source publication change

A new read-only post-processing module handles three narrow **source-returned** fact classes:

1. Exact numeric device attribute ranges from successful projected inventory pages. Deduplicate native IDs, validate offset/count/total/hasMore metadata, classify missing versus nonnumeric, compute inclusive result and state incomplete/unseen coverage. Contradictory pages fail closed. No guessed values for unread devices.
2. Focused stored-current attributes when an otherwise empty first answer has valid successful label-scoped inventory receipts. The publication is explicitly PARTIAL and never treated as an independent dated device event.
3. Requested source-grouped native past logs from the already existing safe original log fallback. Use the largest independently validated single original receipt instead of combining possibly overlapping pages. Separate actual returned rows, reported matches and aggregate total with unspecified scope.

No extra source read, retry, model round, model provider change, write, native authorisation change, V1 change, heating schedule or user automation change. All original tool results remain in Technical JSON unchanged. This does NOT repair history continuity, memory KB calculations, causal initiation or the 53-case benchmark.

## Review and promotion boundary

Synthetic regression tests may check outputs against fictional sources, but do not prove that model answers improved on live installations. The original owner alpha154 captures are post-hoc diagnostic baselines and must **never** be replayed, refrozen or promoted as prospective alpha155 first attempts.

Before promotion, prepare a distinct alpha155 version and unseen sealed prospective pack, run exact-head GitHub CI, verify the dedicated token's true Read ON / Write OFF enforcement, and independently source-grade the new installed original first answers. Retain the charter: **at least 90% grounded atomic factual claims, at least 80% useful complete first answers, zero unsupported definite causes and zero write/approval regression**.
