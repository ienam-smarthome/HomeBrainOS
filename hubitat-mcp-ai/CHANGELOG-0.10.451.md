# Hubitat MCP AI 0.10.451

- Add deterministic semantic time windows for named-device history questions: `last night`, `yesterday`, `this morning`, `since midnight`, `today`, and explicit `between <clock> and <clock>` ranges.
- Define `last night` as the previous local calendar day at 18:00 through the current day at 08:00, capped at the current time while that overnight window is still in progress; explicit clock ranges override that default.
- Widen the single upstream `hoursBack` history read only far enough to cover the requested local window plus a boundary buffer, then clip interval arithmetic to the exact requested start/end locally.
- Establish the state at a window boundary from a predecessor event when available, or from the first binary transition only when the returned event page is known complete back to the requested start.
- Keep busy/truncated 50-event pages conservative: if the source does not reach the requested start, mark temporal coverage partial and the total as a lower bound rather than inventing missing state.
- Expose resolved window start/end, boundary basis, coverage, and deterministic totals in bounded technical evidence while preserving the 0.10.450 final-answer duration consistency guard.
- Add regression coverage for semantic parsing, explicit clock ranges, request-context isolation, clipped interval arithmetic, boundary inference, truncation handling, and service-level `hoursBack` widening.
