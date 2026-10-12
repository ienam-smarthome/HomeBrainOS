# HomeBrain 0.17.23 — Exact requested OFF boundary in causal discovery

- Fixes a causal evidence-selection regression: the upstream event source correctly retained multiple historical OFF events, but HomeBrain's reporting-source correlation was anchoring its local sensor checks to the *latest* OFF rather than the uniquely requested historical OFF.
- Propagates the event-specific, verified focal OFF boundary from the subject timeline into boundary producer selection, state-reporting-source checks, and historical `since`/`until` sensor retrieval.
- Explicit exact-time questions with no uniquely observed OFF event no longer silently substitute another, newer event.
- Broad, untimed "why did this light turn off?" questions retain the existing latest-observed-transition behaviour.
- Adds multi-OFF, same-day regression tests for both the producer matching utility and the host orchestration handoff, including fail-closed tests.
- Read-only: devices, rules and hub settings are not modified.

**Evidence retention note:** bounded `since`/`until` queries cannot retrieve events already removed from the upstream Hubitat store. This fix ensures the requests target the correct historical interval and makes source-coverage checks meaningful.
