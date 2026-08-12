# 0.10.421

## Why this release

This is a safety-relevant hotfix. After 0.10.420 (which fixed "enable it"
sending the wrong `appId`), live testing hit a more serious problem on the
very next attempt: the assistant replied "Enabled the '01. Humidity
Controller' app." while the technical-details payload showed
`model_rounds: 1`, `tool_calls: 0`, and `evidence: []` -- no tool had ever
actually run. The model fabricated a mutation success with nothing to back
it.

## Fixed

**A write-classified reply with no successful mutating tool receipt is now
refused instead of returned as if it succeeded.** `request_class` becomes
`"write"` the moment a mutating tool call is *attempted* in the
tool-calling loop -- including one that names an undeclared tool, which
can never actually execute and therefore never produces a result. Once
that happens, the model is free (on a later round with zero tool calls) to
narrate whatever it wants, and the existing grounding check only asks "did
*any* live evidence exist this turn," not "does this write claim have a
real mutation behind it." The system prompt already instructs the model
never to claim a mutation succeeded without a confirming tool result, but
nothing deterministically enforced it.

The tool-calling loop now checks, at the exact point it would otherwise
return the model's own wording: if this turn ever attempted a mutation,
was that mutation actually confirmed by a successful tool receipt with
`mutates: true`? If not, the reply is replaced with a clear refusal
("I could not verify that this action actually ran on Hubitat -- no
successful tool result confirms it, so I will not report it as done.")
instead of the model's unconfirmed narration.

This check is scoped precisely to the fabricated-success shape and does
not disturb legitimate non-success write outcomes that already have their
own honest messages -- for example a rejected confirmation ("a unique
session_id is required") or a confirmed action that genuinely failed
("did not succeed: ..."). An earlier draft of this fix tried to catch
those cases with a message-wording blacklist and broke two existing tests
because there is no way to enumerate every legitimate failure phrasing;
this release's fix instead checks the actual evidence receipts, which is
exhaustive by construction.

## Validation

- `python -m pytest -q` -- 869 passed. New coverage in
  `tests/_entity_first_orchestrator_cases.py`
  (`test_unverified_mutation_claim_is_refused_not_narrated`) reproduces
  the exact live failure shape: a mutation attempt naming an undeclared
  tool, followed by a no-tool-calls round narrating success. Confirmed
  this test fails against the pre-fix code (reverted locally to verify,
  reproducing "Enabled" in the returned message) before restoring the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.421
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
