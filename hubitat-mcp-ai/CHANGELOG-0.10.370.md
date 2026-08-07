# 0.10.370

## Fixed

Live testing of 0.10.369 against the real WebUI surfaced two further bugs,
both observed directly rather than inferred:

1. **A routine light/switch command failure was badged "Success."** Asking
   "living room light" produced a green `Success` outcome badge next to
   the message "Failed: Livingroom Light 2 and Livingroom Light 1." —
   `DeviceControlService.execute()` correctly built its `succeeded`/`failed`
   result lists and `_present_control()` correctly rendered the "Failed:"
   text, but neither a dispatch failure (`command_sent` False) nor an
   unverified-state result touched any of the fixed outcome counters that
   `request_outcome_policy.classify_completed_request()` reads. With none
   of the six counters incremented, classification fell through to its
   `"success"` default regardless of what the message actually said. This
   is the same class of gap `ConfirmedActionCoordinator` already closed
   for the sensitive-mutation confirmation path via
   `mutation_verification_failures` — the routine control path never had
   an equivalent.
2. **A bare "temperature" query answered from the outdoor weather device.**
   The 0.10.369 fix scoped `DeviceQueryService.resolve_device` to disambiguate
   bare attribute words across multiple *indoor* reporters, but a bare
   "temperature" query never reached that function at all — the system
   prompt told the model to call `homebrain_weather_snapshot` for "current
   weather or weather-device questions" without requiring an outdoor-specific
   qualifier, so the model applied it to an unqualified "temperature" too.
   Live-tested: it answered "20°C" from the Open-Meteo outdoor forecast
   device while every actual indoor sensor read 24-28.5°C at the same
   moment (Livingroom temp & humidity 27.8°C, Hallway Meter 28.5°C,
   Bathroom meter 27.2°C, Thermostat 24.0°C, etc.) — a materially wrong,
   confidently-stated answer with zero disambiguation.

## Fix approach

**Bug 1 (deterministic, not prompt-only):** added a new fixed counter,
`device_control_failures`, incremented once in
`DeviceControlService.execute()` whenever its `failed` result list is
non-empty (covers both the outright-dispatch-failure and the
sent-but-unverified cases), wired into `RequestMetrics.ALLOWED_COUNTERS`,
`request_outcome_policy`'s precedence table (classified `"failed"`,
alongside `mutation_verification_failures`), and
`technical_metrics_presenter`'s counter labels ("Device control
failures"). This is a plain counter/classification fix with no
probabilistic component — any routine control failure now flips the
outcome badge, regardless of wording.

**Bug 2 (prompt guidance — known to be probabilistic, not a guarantee):**
tightened the system prompt's weather-routing rule to require the user
actually say "weather", "forecast", "outside", or "outdoor" before calling
`homebrain_weather_snapshot`, and added an explicit instruction that a
bare, unqualified reading word should go through `homebrain_resolve_device`
instead, where the 0.10.369 disambiguation guard already applies. As with
the prompt-only mitigation flagged in the 0.10.367 changelog, this is a
steering change, not a deterministic gate -- CONTRIBUTING.md's
architectural rule against gating *safety* behavior on prompt wording
doesn't apply to ordinary tool-selection routing, but the model can still
occasionally choose the wrong tool despite the instruction. A fully
deterministic fix would mean adding a dedicated fast path for bare
attribute words ahead of the model's tool-selection loop entirely,
mirroring `contextual_read_fast_path.py`'s existing pattern; that is a
larger change and is being left as a tracked follow-up rather than rushed
into this release.

## Validation

- `python -m pytest -q` — 627 passed (4 new: two `test_device_control_service.py`
  cases proving `device_control_failures` increments on a dispatch failure
  and stays absent on success, one `test_request_outcome_policy.py` case
  proving the new counter classifies as `"failed"`, one
  `test_agent_prompt_policy_manifest.py` case asserting the tightened
  weather-routing wording is present in the system prompt).
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` — 0.10.370
- `python scripts/analyze_imports.py` — `orphan_modules: []`
- Live re-check pending: since bug 2's fix is prompt-only, it should be
  re-tested against the real WebUI with "temperature", "humidity", and
  "what's the weather outside" the same way 0.10.369 was, to confirm the
  model actually follows the tightened wording rather than assuming it
  does from the text change alone.
