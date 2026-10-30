# v0.18.256 — Recover incident evidence when the live history has rolled over

## What failed in the live test

The original MCP agent correctly resolved two independent target light IDs and read 11 switch events for each. Those events were from **after** the requested 14:50–15:30 window. With zero events inside the focal window, `collect_unified_evidence` returned `None`; `recover_group_journal` required that same evidence packet, so it never checked the previously successful Historical Journal. The response therefore incorrectly described a complete historical evidence gap.

## Architectural correction

- A successful, device-scoped, independently identity-verified history read can now establish **source coverage of the target but not coverage of the historical incident**. Even when no event from that window survived, the evidence packet preserves the verified identity and explicit missing-history status.
- Journal eligibility no longer depends on having at least one in-window surviving command or state report. When a target's switch history is empty for the incident period, the model's original bounded read-only journal path may recover its independently source-timestamped events.
- A recovered Journal switch observation can inform the original model's existing next-read decision, including an independent sensor/controller investigation. No fixed device IDs, guessed timestamps or new tool permissions are introduced.
- Both native history and Journal are still marked **historically incomplete**. Collector-only reception observations are not promoted to source clock events, and an empty archive does not prove a device was inactive.
- No changes to automation control, device writes, authentication, background collection or the Hubitat host.

## Validation

Regression tests reproduce two separately resolved lights whose native histories contain *only newer events*, verify exact-date/time-safe archive recovery, source vs reception timestamp classification, idempotent journal querying and safe failure with insufficient identities. Full repository CI must pass before merging.

The underlying initiating controller may remain unknown; this release repairs evidence retrieval, not causal attribution by assumption.
