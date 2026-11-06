# HomeBrainOS v0.18.442 — source-scoped historical log reporting

## Live 0.18.441 observation (6 November 2026)

The user supplied a read-only ordinary Ask response and full Technical JSON
for 5 November 16:30–16:53 GMT. HomeBrain safely withheld unsupported claims
that a reboot purged historical messages and preserved three typed system/
location events. The MCP actually executed TWO different native-log reads:

- A bounded `hub_get_logs` request with since/until and no explicit mode
  (the upstream MCP tool defaults to **past**): one successful query, zero
  matching returned messages, 10,639 raw source rows *before* filtering.
- An unbounded explicit `mode="past"` sample with limit 10: one successful
  query returning 10 timestamped, device-identified messages, 10,640 raw
  source rows reported. This does not establish oldest retained time.

The v0.18.441 answer incorrectly attached the zero-match/10,639 metadata to
**both** "Past historical log" and "Generic bounded historical log" headings
because it reused the same globally aggregated bounded-page observations for
each mode. This duplicated the *reporting*, **not** the executed MCP request.
The next checks also requested another small recent sample that had already
been read.

## General correction

- Keep each successful native past-log page tied to its actual call mode,
  window type and returned source metadata. The existing global fields remain
  for backwards compatibility; new `mode_page_observations` distinguishes
  explicit `past` samples from date-bounded omitted/default-mode reads.
- Render evidence independently under each successful query:
  `past` unbounded sample reports 10 recent returned rows without inheriting
  the historical zero-match page, and default past bounded read reports its
  own zero matching rows and pre-filter total exactly once.
- When a recent sample already exists, suggest checking the oldest/latest
  available source time and hub timezone rather than re-running the same
  recent sample. If none exists, a small read-only recent sample remains a
  valid first check. An empty bounded page alone is not evidence that logs
  never existed or were purged.
- Dedicated incident Technical JSON includes mode-scoped observations as well.
- Regression fixtures cover the exact 0.18.441 two-query pattern, mixed
  positive/empty windows, failed or unverified reads, no private message
  disclosure, and existing case safety/compatibility.

## Limits and release gate

The original memory-consuming application, historical retention cause, and
oldest retained native log timestamp are still **unverified**. This release
does not recover old messages, change the model's claim guard, add MCP or
provider reads, alter write permissions, or reintroduce a complex-investigation
latency target. 40.3 seconds in the previous run is an observation, not an
acceptance threshold.

Green tests mean code-level validation; improvement in real user-graded first
answers is **not yet measured**. Roll back if source metadata appears under
the wrong query mode, any unsupported causal attribution is published, or
historical/private data appears in added technical fields.
