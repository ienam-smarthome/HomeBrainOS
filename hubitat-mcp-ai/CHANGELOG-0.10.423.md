# 0.10.423

## Why this release

After 0.10.422 fixed the wrong-`appId` bug, live testing confirmed "enable
it" now genuinely succeeds -- but the technical-details panel still showed
`evidence: []` and `tool_calls: 0` for a confirm that really did run a
successful mutating tool call. This release closes that observability gap
so the technical details reflect what actually executed.

## Fixed

**A confirmed action's real tool-call evidence was silently discarded
before it ever reached the response.** `_resolve_pending_confirmation`
intercepts a "confirm" reply before any other deterministic fast path
runs -- including the base `process_user_request_result` /
`DirectOutcomeContext` wrapping that normally opens the request-scoped
evidence receipt list via `EvidenceRecorder.begin()`.
`ConfirmedActionCoordinator.resume()` does call `self.evidence.record(...)`
for the real tool execution it runs, but `EvidenceRecorder.record()`
silently no-ops when no receipt list has been started yet (`if receipts is
None: return`) -- so every receipt from a confirmed action was discarded
before it could be read back, and the outcome hardcoded `evidence=[]`
regardless of what actually ran, which in turn made the reported
`tool_calls` metric always read 0 (it's derived from
`len(outcome.evidence)`).

The confirm-resume branch now opens the same evidence scope
`DirectOutcomeContext` already opens for every other deterministic fast
path, executes the confirmed action inside it, and reports the real
receipts. This is purely a reporting fix -- the actual tool executions and
their real success/failure were never affected, only what showed up in the
technical-details panel afterward.

## Validation

- `python -m pytest -q` -- 871 passed. New coverage in
  `tests/test_homebrain_agent.py`
  (`test_confirm_resume_reports_real_evidence_not_a_hardcoded_empty_list`)
  reproduces the exact live gap: a successful firmware-update confirm now
  reports a real `hub_update_firmware` receipt with `success: true` and
  `mutates: true` instead of an empty evidence list. Confirmed this test
  fails against the pre-fix code (reverted locally to verify, reproducing
  `evidence: []`) before restoring the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.423
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
