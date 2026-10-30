# v0.18.258 — Source-attested input relevance, not just nearby sensor timing

## What the live investigation proved
v0.18.257 recovered the complete available Bathroom switch timeline and included independent Bathroom Hi-P motion observations from device 7746. But the sensor's original event records explicitly notified app 4014 (Shower), while app 4013 issued the observed Bathroom brightness commands. The model/digest did not preserve these distinct roles, and a same-room motion observation could be mistaken for an actual control dependency.

## Architecture
- Project **typed command issuer** and **event-notified app listener** IDs directly from successful, device-scoped, source-timestamped native MCP event receipts. The existing event-summary projection deliberately excludes `triggered[]` payloads; this release captures only validated app IDs before that sanitization.
- Relate each independently observed sensor input to actual target command apps and target event listeners; classify a shared target command app, a shared target listener, a different observed association, or insufficient association evidence.
- Feed the same typed relationship packet into the *original* model evidence and in-loop cross-source discovery checkpoint.
- Preserve the relationship distinction in the source-grounded Historical Journal final explanation alongside the source-timed sensor input events.
- **Never** promote an event subscriber to an initiating controller, a shared app to proof of historic execution, or disjoint observed app IDs to complete proof that no alternative path exists.
- No new MCP tools, agent routes, permissions, device configuration changes or Hubitat writes.

## Tests and boundaries
Cross-domain regressions include inputs notifying a different app from the target's recorded command app, a genuinely shared app lead, exclusion of mutating tool receipts, and out-of-window input notifications. A model-selected upstream trace is still necessary to identify the original initiator definitively.

Live validation should verify that the answer separates Bathroom Hi-P -> Shower app 4014 observations from Bathroom Light 1/2 <- recorded app 4013 brightness commands, instead of presenting all Bathroom sensors as equally causally relevant.
