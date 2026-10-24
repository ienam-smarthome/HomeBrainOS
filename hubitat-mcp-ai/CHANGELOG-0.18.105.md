# HomeBrainOS 0.18.105 — Fast bulk confirmation previews without reducing write safety

## Live 0.18.104 follow-up (24 October 2026)

Two bulk Internet-control confirmation prompts took **27.56s OFF** and **26.07s ON**, spending 27.3s and 25.8s in MCP HTTP despite zero logged tool calls. Both properly returned needs_input and performed no writes. Version 0.18.104 preferred the TTL-checked identity cache, but the exact target checker rejected compact identity records lacking the detailed commands list and fetched the slow full paginated device manifest.

After user approval, the attached OFF and ON execution receipts reported successful commands for 11 Internet-blocking switch devices. Each full confirm-and-execute turn took ~29.1 seconds, including pre-write detailed identity refresh and ~5.5s of observed device-control work. Cumulative MCP queue/HTTP measurements are not additional wall time.

A third read-only test, "turn off everything in Appliances except the freezer", produced candidate targets while the host blocked an unauthorised write (proposal_write_attempts_blocked=1). Generated wording "I will turn off..." was misleading because no write was issued.

## Changes

- **Provisional approval preview:** Accept a fresh complete structural identity with exact unique IDs/labels and the standard Switch capability for a proposed ON/OFF operation even when the identity omits its commands property. An explicitly present empty or contradictory commands list cannot grant this preview exception. Staging never dispatches a device command.
- **Post-confirmation write validation unchanged:** After explicit same-session approval within 120 seconds, force a fresh detailed manifest and verify the exact approved ID/label set and actual supported native command per device. Never elevate provisional selection to write authority.
- **Performance diagnostics:** Distinguish control_confirmation_preview_cache, control_confirmation_manifest_fallback and control_confirmation_fresh_revalidation.
- **Blocked-write response integrity:** If a model write proposal was rejected and there is no mutating evidence, replace misleading "I will turn off" text with a clear "Nothing was changed" warning. Preserve legitimate read answers and do not claim zero writes if any write receipt exists.
- **Mocked MCP regressions:** Verify fast compact staging without detailed reads, capability mismatch fails closed, explicit empty commands cannot stage, full command capability is verified after approval, and direct commands remain unaffected.

## Limitations

An approved command turn can still take ~29 seconds because it intentionally refreshes detailed identity evidence before executing. Further optimisation requires independent evidence for fresh command capability, without sacrificing safety or increasing live Hubitat write concurrency. This release is code-only; no live Hubitat device, Internet control, rule or setting has been changed by these commits.
