# 0.10.424

## Why this release

With the app disable/enable flow finally confirmed working end to end
(0.10.419-0.10.423), this release is a deliberate audit-and-harden pass
rather than a response to a single new live bug report: a systematic check
for other instances of the two bug classes found this cycle (evidence
silently dropped before reaching a response; a model's own narration
trusted without checking real tool-call evidence), plus a general code
quality sweep (dead code, inconsistent error handling, test coverage,
stale docs, config/version alignment).

## Fixed

**The unverified-mutation refusal from 0.10.421 didn't cover two other
loop exit points.** 0.10.421 added a check, right before the normal
"model returned no tool calls" reply, that refuses instead of narrating
when this turn attempted a mutation (even via an undeclared tool name,
which fails closed to a sensitive-write classification without ever
executing) but no successful tool receipt confirms it. A follow-up code
audit found `_final_answer` -- the helper used by two OTHER loop exits,
the duplicate-tool-call-signature early return and the tool-round-limit
exhaustion fallback -- returned raw model narration through the exact
same gap. Both now go through the same check, centralized inside
`_final_answer` itself so every current and future caller is covered by
construction instead of needing to remember to add it individually.

**A hub/network failure while checking for duplicate rule names was
completely silent.** `RuleAuthoringService._existing_names()` caught any
`hub_read_rules` failure and returned an empty set with no logging at
all, unlike every other best-effort fallback elsewhere in this codebase
(`hub_info_service.py`, `device_query_service.py`,
`mcp_agent_orchestrator.py`), which all log before falling back. A rule
still gets created in this case (duplicate detection just can't be
verified that turn), but the failure now leaves a trace instead of
vanishing.

## Audit summary (no code change needed)

- Dead code: none found (`analyze_imports.py` reports 0 orphan modules;
  manually verified 13 apparently-unused top-level names were all false
  positives -- dataclasses used via method calls, or internally-used
  helpers).
- Test coverage: all 49 live app modules have corresponding test
  coverage; 873 tests collected with zero collection errors going in.
- Stale docs/TODOs: none found; the only `TODO`-adjacent grep hit was a
  user-facing response string, not a dev comment.
- Config/version consistency: clean going in
  (`validate_addon.py`/`validate_release_consistency.py`/
  `analyze_imports.py` all passed before this release's own version bump).

## Validation

- `python -m pytest -q` -- 874 passed. New coverage:
  `tests/_entity_first_orchestrator_cases.py` adds
  `test_duplicate_call_signature_exit_also_refuses_an_unverified_mutation`
  and `test_tool_round_limit_exit_also_refuses_an_unverified_mutation`,
  each reproducing one of the two newly-covered `_final_answer` exit
  points; confirmed both fail against the pre-fix code (reverted locally
  to verify) before restoring the fix. An existing crash-regression test
  (`test_undeclared_tool_call_does_not_crash_causal_bypass_check`) had its
  expected reply text updated -- its fixture happens to also hit the
  duplicate-signature exit, so it now correctly receives the deterministic
  refusal instead of passing the model's raw content through; the crash
  regression itself is unaffected. `tests/test_rule_authoring_service.py`
  adds `test_existing_names_lookup_failure_logs_and_falls_back_not_crashes`,
  confirmed to fail against the pre-fix silent-swallow before restoring
  the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.424
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
