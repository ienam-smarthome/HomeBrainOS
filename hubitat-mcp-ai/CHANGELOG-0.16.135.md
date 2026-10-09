# HomeBrainOS v0.16.135 — bounded investigations and progress

## Fixed
- Read-only whole-hub optimisation and comprehensive audit requests now have a configurable **90-second overall deadline**. When source evidence has already been collected, a timeout returns a short receipt-based partial result instead of unverified model advice; otherwise it returns a clear 504 with retry guidance.
- Final performance AI synthesis is separately limited to **30 seconds**. If Gemma takes too long, HomeBrain returns the verified-source list and an explicit "AI synthesis did not finish" explanation rather than spinning indefinitely.
- The Ask interface polls a per-session/per-request progress endpoint during work and displays stages such as collecting Hubitat data, analysing jobs and generating recommendations, with elapsed seconds.
- Existing supersede/disconnect cancellation is preserved and previous-task waiting is bounded to 2 seconds. Completed progress entries are removed.
- A logging filter redacts access tokens from emitted httpx request URL records. Any credentials previously exposed in downloaded logs still need to be rotated.

## Configuration
- `investigation_deadline_seconds`: 90 (whole-hub review and comprehensive diagnostics).
- `performance_synthesis_timeout_seconds`: 30 (final AI synthesis only).

## Safety and limitations
- No Hubitat device, rule or app is changed by this patch.
- Partial results do not invent savings or reuse unverified model draft conclusions.
- Some client requests may have no verified checkpoint at deadline; those return a bounded error instead of a fabricated result.
- Timing budgets apply to read-only comprehensive investigations, not mutating actions.
- The underlying tool gateway and network may still cause individual slow calls, so latency metrics remain important.
