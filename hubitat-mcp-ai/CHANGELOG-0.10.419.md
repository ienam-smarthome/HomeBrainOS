# 0.10.419

## Why this release

This is a hotfix for a crash introduced by 0.10.418's own fix. Applying
0.10.418 and testing "enable it" returned a raw 500 error: `cannot access
local variable 'causal_history_bypass' where it is not associated with a
value`. 0.10.418 correctly let pronoun-only requests fall through to the
model's tool-calling loop instead of failing in a doomed device search --
but that loop had a pre-existing latent bug that nothing had exercised
until now.

## Fixed

**`causal_history_bypass` could be read before it was ever assigned.**
In the orchestrator's per-tool-call loop, this variable was only set
inside the branch handling a *declared* tool's result, but read
unconditionally later in that same loop iteration. A model tool call
naming an undeclared tool takes an earlier branch that never touches it
at all -- previously latent because nothing reaching the model loop
happened to call an undeclared tool as its first action of a round.
0.10.418's pronoun-target fix was the first change to route a request
("enable it") into a path where the model's first tool call landed on
this exact gap, crashing the whole request instead of returning a normal
tool-error reply. The variable is now explicitly reset at the top of
every loop iteration, so each tool call's bypass decision is independent
and never leaks stale state (or crashes) across calls.

## Validation

- `python -m pytest -q` -- 866 passed. New coverage in
  `tests/_entity_first_orchestrator_cases.py`: a model tool call naming
  an undeclared tool as the first action of a round no longer raises
  `UnboundLocalError` and instead completes normally. Confirmed this
  test fails against the pre-fix code (reverted locally to verify) before
  restoring the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.419
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
