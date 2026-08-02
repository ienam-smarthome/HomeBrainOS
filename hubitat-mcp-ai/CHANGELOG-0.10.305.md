# 0.10.305

- Record ambiguous device resolutions at the deterministic resolver decision point.
- Count duplicate exact-name collisions and unresolved ranked ties once per decision.
- Do not count successful matches, missing candidates, or events outside an active request.
- Add focused privacy-safe request-metric regression tests.
