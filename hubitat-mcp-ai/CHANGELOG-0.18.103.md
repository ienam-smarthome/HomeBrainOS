# HomeBrainOS 0.18.103 — Immediate control safety boundary

## Reported safety regression

Claude replayed the production agent against a **mock MCP server** with real device inventory labels. It observed unconfirmed device-write requests for conditional phrases such as "turn off the freezer unless it's full", ambiguous questions, and a compound request ("turn on the TV and tell me its power draw"). A bulk Appliances room OFF command included both Freezer and Fridge without approval. Read-only prompts beginning "Allow me to understand" and "Enable me to see" were intercepted by the Internet command fast path.

These are simulated **command dispatches**, not proven physical Hubitat actuation. They are nevertheless high-priority defects in the text-to-write authorization boundary.

## Changes

- Require a single unqualified, non-question control clause before a deterministic or semantic immediate-control path can execute. Subordinate IF/UNLESS/WHEN/AFTER/BEFORE/UNTIL, cancellation, negation, compound AND/BUT, and interrogatives fail closed and pass to ordinary model interpretation.
- Independently revoke model-tool **write authority** from malformed or conditional immediate-control lead-ins. A model-proposed tool call cannot repair missing user consent. Requests to create automation/rules remain separate and continue through the existing native authoring safety and confirmation gates.
- Protect refrigerator/freezer, network/router, camera/security, and hub-like devices by label/capability risk classification. A protected switch command cannot execute from immediate routing without user approval.
- Stage multi-device and whole-room switch commands for confirmation. The staging response names the exact devices and sends no command. Confirmation is session-bound, expires in two minutes, cancels on any other message, and revalidates the same concrete device IDs/labels and supported commands before dispatch. Staging fails closed if a device list cannot be resolved unambiguously or the session is not unique.
- Preserve the usual single-device ordinary switch shortcut, e.g. "turn off the washing machine" or "turn on TV", without a provider round or extra confirmation.
- Prevent read-only "Allow me to understand ..." / "Enable me to see ..." from entering Internet-access command routing.
- Convert the reproduction prompts into explicit pass/fail fake-MCP regressions, including confirmation cancellation and changed identity checks.

## Scope and caveats

No physical home device, hub rule, firmware or network service was changed. The new guard focuses on immediate **device** control; a separate end-to-end audit of every administration gateway and alternative model-triggered write path remains appropriate. The embedded protected-device label categories are a conservative temporary safeguard; a configurable, device-ID-grounded protected-control policy is preferable in a later architecture consolidation. No additional paid model usage is introduced.
