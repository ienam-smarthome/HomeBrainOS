# 0.10.456

History-evidence semantics hardening after the 0.10.455 live soak.

## Changed

- Semantic device-history calls that omit a state attribute now use the full bounded 50-event page. If the returned rows contain exactly one supported binary state attribute (`switch`, `contact`, `motion`, `lock`, or `valve`), HomeBrain derives deterministic temporal analysis from that attribute instead of leaving the model to interpret a generic event list.
- Empty semantic windows can now become complete zero-duration proofs when the source page is complete, no transition occurred inside the requested window, every analysed event is present, and the first binary transition after the window establishes the immediately preceding state. The evidence records `boundaryBasis=first-transition-after-window-inference`.
- A zero-duration result with an incomplete boundary remains a lower bound. The API serialization boundary prevents model wording such as “was not on” or “no recorded events” from upgrading that partial observation into proof that the device stayed inactive for the whole window.
- WebUI clarification metadata (`Device clarification: use exactly …`) is now a request-local hard constraint for model-directed named history/resolution reads. A selected device cannot silently fan back out across the alternatives the user just rejected.
- The generic evidence-review contract now explicitly requires the model to establish that an event occurred in the requested window before spending additional reads investigating its cause.

## Why

Live 0.10.455 testing showed two evidence-semantics failures: Hallway Light 1 had `0s` with `coverage=partial` and `totalIsLowerBound=true`, yet the answer stated it was not on; and a clarified bathroom-fan request queried all three fan alternatives and then claimed there were no Fan Switch events because the model omitted `attribute=switch` and only a 20-row generic history page was analysed. This release fixes those behaviours structurally rather than adding device- or question-specific rules.

## Validation target

- A partial zero history must never be serialized as proof of an inactive window.
- When the first post-window transition proves the preceding state, the same zero history becomes `coverage=complete` and `totalIsLowerBound=false`.
- An attribute-less semantic Fan Switch history should expose deterministic `temporalAnalysis` when `switch` is the only supported binary state attribute in the returned rows.
- After selecting `Fan Switch (Tuya Local)`, model-directed history/resolution calls for `Fan Boost` or `Standing Fan` are not executed.
