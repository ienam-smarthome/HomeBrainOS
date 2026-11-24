# V2 deterministic receipt computation (homebrain_compute_receipt)

**Status:** code candidate, not installed or accepted. No V2 version bump yet.

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
