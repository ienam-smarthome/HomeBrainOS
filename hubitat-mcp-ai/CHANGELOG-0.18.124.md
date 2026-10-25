# HomeBrainOS 0.18.124 — V2 bounded read execution (explicit harness)

## Changes
- Introduces a request-scoped, bounded Investigation V2 async loop driven by
  structured AI-proposed discriminating reads and candidate hypotheses.
- Reuses the existing ToolExecutor and the actual MCP tool manifest for every
  approved read; V2 does not create an independent permission or transport path.
- Adds deterministic caps for model rounds, overall deadline, read count,
  per-read timeout, duplicate requests and verified ID scope.
- Projects raw returned device-event/history, app-config and dated-log source
  data into allowlisted, non-secret typed receipts **before** updating the
  shared case file or showing it to any model.
- Tracks competing hypotheses only as evidence-cited **candidates**; source
  command, device state and transport semantics remain independent. A
  hypothesis never by itself certifies a root cause.
- Preserves the original user question and all observations across rounds,
  including the October overnight incident's command timeline.
- Adds end-to-end fake-MCP tests for tool-call safety, source mismatch,
  cancellation, timeouts, credential exclusion and useful-evidence retention.

## Production boundary
The V2 runner is **explicitly invoked only**. It is not wired into routine
HomeBrain chat, background timers, Hubitat writes or the V1 final-answer path.
There is no claim of improved production answer quality from this release.
The next stages are model-client adaptation, hypothesis/claim auditing and
read-only shadow evaluation before any cutover.
