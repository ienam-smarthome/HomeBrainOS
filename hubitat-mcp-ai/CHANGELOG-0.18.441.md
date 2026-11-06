# HomeBrainOS v0.18.441 — source-retention claim coverage

## Source-real failure

The user-submitted v0.18.440 read-only historical-log investigation successfully
queried a recent native past-log sample (20 timestamped device-identified rows)
and a bounded past-log window for 5 November 2026 16:30–16:53 GMT
(zero matching messages from 9,867 raw source rows before filtering).
Independently verified typed Hubitat events included lowMemory at 16:41:40,
sunriseSunsetUpdated at 16:44:20 and systemStart at 16:52:15 UTC.

The model published unsupported claims that "a log purge occurred, likely
triggered by the hub reboot" and that "the diagnostic log buffer ... has been
cleared". The v0.18.440 guard recognised some explicit "logs were purged
because of reboot" forms but missed loss-as-noun and buffer-cleared forms.
The source data does not prove the deletion mechanism, the oldest retained
native timestamp or the original memory-consuming process.

## Change

- Generalise the existing **unresolved investigative source-retention**
  publication guard to unqualified assertions that native logs, messages or
  history were purged, cleared, erased, deleted, rotated or removed. Include
  variants with the causal connector omitted, such as "a log purge occurred".
- Do **not** rewrite explicitly uncertain hypotheses ("may", "could",
  "unverified", "not proven") or explicit negative statements.
- When an unsupported claim is detected, the existing safe reconstruction
  preserves actual recent-page and zero-match bounded-page numeric receipts,
  separate pre-filter source totals, the authenticated chronological Hubitat
  event timeline and read-only next checks. The missing historical retention
  mechanism and original memory consumer remain **unverified**.
- Preserve the existing no-extra-MCP-calls, no-hub-writes, no-polling, no
  provider-routing-change boundaries. Do not reintroduce a fixed complex
  investigation latency target.

## Tests and limits

Synthetic regression tests reproduce the full v0.18.440 public phrasing
and the typed source structure, and check independent formulations, negations,
tentative hypotheses, unrelated completed cases and failed source receipts.
These are code tests, **not evidence** that the original historical logs
have been recovered or that model answer quality has improved in the live
deployment. Re-run the same read-only question and full Technical JSON after
deployment. If the guard still misses unanticipated paraphrases, improve the
general evidence-to-claim validation rather than introducing
incident-specific culprit rules.

Rollback on privacy leakage, unsafe fact promotion, unwarranted suppression
of verified conclusions or a regression in read-only/control routing.
