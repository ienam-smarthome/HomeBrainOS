# HomeBrainOS v0.18.187 — Native device-mode evidence and read efficiency

## 28 October 2026 live results

Native V2 investigated Google Nest Hub 7934 in 35.239 seconds. A bounded
read successfully returned 71 warning rows grouped into 43 runQ log rows,
27 excessive hub-load log rows, and one setVolume log row, reporting
representative durations of 147,429ms and 124,842ms. These are source
log-row counts, **not** independently confirmed counts of distinct executions.
NetworkStatus=online and status=idle were source-reported attributes only.
The investigation subsequently spent time on multiple device-mode calls,
three failed hub_get_device reads, one unrecognised Logs-page summary and
an 8.005-second final synthesis timeout.

## Shared architectural improvements

- A bounded, privacy-filtered device evidence adapter now extracts driver
  identity, configuration field names, preference metadata, selected
  details/section status and driver-source availability instead of stripping
  entire configuration/details mode payloads. It never forwards arbitrary
  secret preference values, raw driver code, URLs or device addresses.
- Focused evidence summaries now include returned device-mode metadata,
  allowing the model to reason about whether an independent driver/source
  read is necessary. The existing model still chooses the next tool.
- A scoped read-failure circuit breaker prevents a model from repeatedly
  executing different variations of the same operation for the same verified
  target after two failures. It does not block distinct read operations.
- When a model has exhausted its investigation budget or repair paths after
  retrieving BOTH target-specific warnings and a current device snapshot,
  the host can immediately return a source-backed conclusion instead of
  spending another eight seconds on tool-free synthesis likely to time out.
  The skip reason and target-operation failures appear in diagnostics.
- Distinguish Logs-page summary objects lacking log severity/message from
  actual log records. Such records are explicitly marked uninterpretable;
  they cannot be used as proof of an empty WARN/ERROR history.
- Regression tests use the reported Google Nest Hub live read pattern and
  include metadata redaction, section evidence, scoped failures, synthesis
  bypass and unreadable Logs-page samples.

## Evidence and safety limits

- "43 runQ warnings" means 43 returned log **rows**, not 43 separate
  independently verified slow invocations. The exact internal cause is not
  verified until driver code or independent execution traces are inspected.
- A live online/idle network status does not refute slow driver operations.
  Hub-wide performance impact requires independent hub metrics.
- Driver/configuration details are intentionally projected as safe metadata,
  not raw code, which the model must seek through the appropriate read-only
  source tool if available.
- These changes affect only the experimental Native V2 read agent. No
  Hubitat writes or production Main Ask changes. CI tests do not replace
  live validation.
