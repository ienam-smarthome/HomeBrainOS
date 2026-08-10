# 0.10.403

## Why this release

Finding #14 from the 2026-08-09 code review: evidence grounding
(`grounding_policy.py` / `live_evidence_authority.py`) only checks that
*some* live tool call succeeded this turn, never that it actually backs
the specific claim in the answer -- a model that read Device A's live
state could still answer a question about Device B and pass grounding
untouched. The review flagged this as architectural, not a simple fix,
and asked for a scoping decision rather than a blind patch.

Full claim-to-evidence verification (extracting every factual statement
and matching each to specific evidence) was considered and set aside:
it touches the core answer-acceptance path with no existing test
harness for that scope, and carries real risk of over-refusing valid
answers. Instead, this release ships the narrower option: a
device-name cross-check that catches the clearest failure mode
(confidently naming one device while this turn's evidence is about a
different one) without touching aggregate, comparative, or
device-less answers.

## Added

**Device-claim grounding.** New module `device_claim_grounding.py` adds
one further check on top of the existing has-any-live-evidence
grounding, wired into `mcp_agent_orchestrator.py`'s model tool-calling
loop right after the existing capability-denial check. When the model's
final answer, with no further tool calls, names a specific device by
its known inventory label, and this turn's successful evidence receipts
carry a *different* device's id, the claim is treated as ungrounded for
that device: the model gets one retry with an explicit instruction to
fetch evidence for the named device, then a hard refusal if it repeats
the same or a different unverified device claim.

Device ids are read directly from each successful receipt's tool-call
arguments (searching both bare and gateway-wrapped `{"tool": ...,
"args": {"deviceId": ...}}` shapes), not inferred from prose -- this is
a factual identifier check, not natural-language claim extraction.

**Deliberately narrow scope, documented as a known limitation:** the
check only fires when this turn actually collected device-scoped
evidence at all (a turn with none is left to the existing
has-any-live-evidence check); it only recognises devices by their exact
known label, and it does not distinguish a genuine factual claim about
a device from an incidental comparative mention ("unlike the Front
Door, the Kitchen Light is on" can still trigger a retry if only the
Kitchen Light was read this turn). The retry instruction is harmless in
that case -- it simply asks the model to also read the mentioned
device -- so this tradeoff was accepted in exchange for a
deterministic, low-risk check with no NLP claim extraction.

## Validation

- `python -m pytest -q` -- 774 passed (15 new: 11 unit tests in new
  `tests/test_device_claim_grounding.py` covering id extraction from
  nested gateway arguments, mismatch detection, the short-label
  false-positive guard, and the one-retry-then-refuse policy; 4
  end-to-end integration tests in new
  `tests/test_device_claim_grounding_integration.py` driving the real
  model tool-calling loop through `mcp_agent_orchestrator.UnifiedMCPAgent`
  -- wrong-device retry-then-accept, wrong-device retry-then-refuse,
  correct-device immediate accept, and no-device-named unaffected).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.403
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- `docs/RUNTIME-MODULE-MAP.md` updated with the new
  `device_claim_grounding.py` row (required for
  `test_runtime_modules_match_canonical_module_map` to pass).

## Still open

The 2026-08-09 review's Tier 1/2/3 findings are now fully closed
(0.10.397 through 0.10.402), and finding #14 has this partial fix. No
further items from that review remain scoped for a release unless
raised again.
