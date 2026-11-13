# HomeBrainOS v2 alpha.76 — Structured native rule approval

**13 November 2026 — source-only development; no live hub/router change.**

## Why

Alpha.75's one-off timer safety guard analysed natural-language request wording to reject unrequested rule writers. This created an inconsistent authorization boundary: a numeric interval such as "after 2 minutes" could be recognised but "after two minutes" could be missed. `CONTRIBUTING.md` requires mutation authority to come from actual tools and structured arguments rather than free-text regex classifications.

## Repair

- Identify **recognised native persistent-automation writers** from the actual selected MCP tool or gateway leaf. Do not read the question, history or model's proposal text to decide authorization.
- Require **independent operation-specific approval** in the existing interaction UI even when `confirm` is absent. The pending approval is bound to the request ID and the selected operation's native arguments. Show proposed trigger/actions and warn that conversational "yes" does not constitute approval.
- Decline or missing UI callback => **no native rule write**. A user's explicit approval allows the normal upstream permission, backup, schema and confirmation checks to operate; it is not a promise of validity or correctness.
- The model remains responsible for choosing an actual actuator and native command. **No new scheduler, automatic alternate command, timed-unblock feature, controller mapping or rule authoring**.
- Direct device-native delayed commands remain on the unchanged path. Native rule response `stored` and `activated` attributes are distinct from proof of a fired trigger.

## Test and acceptance boundary

Synthetic coverage: direct and gateway-selected writers, no `confirm`, "2 minutes" / "two minutes", chat "yes", explicit rejection, approved native rule, missing UI callback and no approval for a native one-shot device timer. No real devices are controlled.

**Limitation:** The new boundary ensures separate human approval of an actual writer; it **cannot automatically prove** a proposed rule's trigger is what the user intended. If the assistant invents a mode-change trigger for an ordinary one-off timer, the user must **decline the UI approval**. Underlying MCP permissions remain authoritative for other tools. The alpha.74 accidentally activated Hubitat Visual Rule is not paused/removed by a repository change. The separate wording-dependent **read-only discovery eligibility** in `control_surface_recovery.py` remains for a later architecture audit.

After exact-head checks and installed approval-UX validation, return to Gate B's fresh 12-case, six-domain, read-only first-answer quality study. Do not count synthetic workflow checks as model reasoning accuracy.
