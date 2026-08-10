# 0.10.402

## Why this release

Picks up four Tier 3 items from the 2026-08-09 full code review (low
confidence / low severity / cosmetic, per that document's own ranking),
bundled into one small release since each is an independent, low-risk,
single-file change. #19 (`MAX_DISCOVERED_GATEWAYS = 2`) was explicitly
documented as a deliberate tradeoff, not a bug, and is excluded.

While re-checking the review's exact CPU-load claim (originally filed
against `technical_metrics_presenter.py`) against the current codebase,
the CPU Load figure has since moved to `homebrain_agent.py`'s
`_hub_health_outcome`, and it turned out to still have a live, real
version of the already-fixed unit-doubling bug -- see below.

## Fixed

**CPU Load could double its "%" suffix.** `homebrain_agent.py`'s hub
health answer builds Free Memory, Temperature, and Database Size through
a shared `field()` closure that strips any unit already baked into the
raw driver value before appending the tracked unit once (the fix for the
live "46.9 °C °C" regression). CPU Load bypassed that guard entirely,
building its "%" suffix with a bare `f"{cpu_percent}%"` -- so a Hub Info
driver reporting `cpuPct`'s `currentValue` as an already-formatted "45%"
(the same pre-formatted-string shape already observed live for
temperature) would have rendered "45%%". `field()` now accepts an
optional `literal_unit` for callers with a fixed unit that isn't sourced
from a companion `data` field, and CPU Load routes through it.

**`confirmation_store.py` didn't strip incidental whitespace from
`session_id` the way `confirmation_policy.py` does.** The policy layer
normalizes with `str(session_id).strip()` before comparing; the store
used a bare `str(session_id)` for its `queue`/`consume`/`cancel` keys.
A caller sending a session id with incidental leading/trailing
whitespace could queue or cancel under a key that never matched the
policy layer's own normalized comparison. Both layers now normalize the
same way.

**Silent confirmation eviction under capacity pressure had no
observability.** When `max_pending_sessions` is reached, the oldest
pending confirmation (which may belong to a different session than the
one whose `queue()` call triggers the eviction) was dropped with no
signal anywhere. Added a `confirmation_evicted` counter, wired the same
way the existing `confirmation_expired` counter is, and surfaced it in
the technical metrics panel. This is pure observability -- it does not
change the eviction behavior itself or affect the triggering request's
own outcome classification.

**Truncation marker mislabeled which content was cut.**
`model_context_policy.py`'s history-bounding loop walks messages
newest-to-oldest; when a message overflows the remaining character
budget, it's that message's own tail that gets cut -- not necessarily
the oldest kept message, and not "earlier history" in the sense the old
marker text ("[earlier history truncated]") implied. Renamed to
"[message content truncated]", kept at the exact same character length
so this wording-only fix does not itself change which messages fit
inside the existing budget.

## Validation

- `python -m pytest -q` -- 759 passed (5 new: 1 CPU-load unit-dedup
  regression test in `tests/test_homebrain_agent.py`; 2 in
  `tests/test_confirmation_store.py` covering the session-id strip fix
  for both `consume` and `cancel`; 2 in
  `tests/test_confirmation_expiry_metrics.py` covering the new
  `confirmation_evicted` counter, both the eviction and no-eviction
  cases; 2 existing truncation-marker assertions in
  `tests/test_model_context_policy.py` and
  `tests/_entity_first_orchestrator_cases.py` updated to the new marker
  text).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.402
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
