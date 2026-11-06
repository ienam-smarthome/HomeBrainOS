# HomeBrainOS v0.18.438 — typed native past-log evidence receipts

## Reason / previous live evidence
The user’s read-only v0.18.436 replay returned successful historical
hub_get_logs(mode="past") and hubEvents calls, but public Technical JSON
only retained result field names, not proof of whether any actual timestamped
app/device message rows had been returned. The ordinary Ask safe causal guard
correctly preserved Hubitat’s explicit critical-memory/reboot warning and
subsequent startup while withholding an unverified original memory consumer.
The same replay recorded one failed synthesis repair. It did not establish
that retained historical app logs still existed.

## General, privacy-safe correction
- Add native_past_log_receipt: an MCP response projection that inspects at
  most 200 actual rows of successful read-only native past results and
  records numeric counts, parseable *hub-local* timestamp presence, verified
  app/dev numeric source markers, pagination and truncation metadata.
- Never copy private message bodies, source display names or raw continuation
  cursors into public evidence receipts. Rows without valid source time or a
  verified typed source marker cannot be promoted to app-specific proof.
- Ordinary Ask source-qualified causal outputs can now report counts of
  actually returned bounded messages without claiming complete retained
  history or identifying a culprit.
- Dedicated incident AI Technical JSON and its safe fact summary retain
  actual returned-page evidence. The current-turn synthesis ledger also
  retains distinct page/window receipts rather than deduplicating them by
  broad log scope.
- Preserve v0.18.437’s chart-axis/grid improvements from the same mainline.
- No new MCP calls, automatic polling, provider calls, paid escalation,
  device/control operations, routing or operational deadline changes.

## Evaluation / risk
Synthetic tests cover the upstream past-log row shape, source identity,
invalid/missing local time, duplicate page coverage, 200-row bounds,
sensitive-message exclusion, guarded ordinary Ask, dedicated incident
output wiring and actual ToolExecutor receipts. These prove code handling
only; the user’s missing 5 November app-log content, underlying memory
consumer and any production model answer improvement are **NOT MEASURED**.
Model assertion safety is unchanged. Do not treat a successful log mode or
one inspected page as whole-history coverage, or hub-local time as UTC.
The failed synthesis-repair reason is not available from the supplied
public receipt and is not modified speculatively here.

Rollback if a receipt publishes private messages/cursors, promotes
unverified source IDs, breaks unrelated read-only calls, or regresses
model safety. Next perform one source-real read-only ordinary Ask versus
explicit incident review and inspect actual nativePastLog metadata; if
messages are absent or retention truncated, preserve that limitation.
