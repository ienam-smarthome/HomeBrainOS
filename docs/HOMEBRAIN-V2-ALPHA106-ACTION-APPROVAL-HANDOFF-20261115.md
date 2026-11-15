# HomeBrainOS V2 alpha.106 — native approval handoff for prose-only confirmations

**15 November 2026; V2 Preview only.** Do not include installed private Hubitat receipts, identifiers, IPs, household names, secret credentials or literal client telemetry in the repository.

## Original failure

In an owner-supplied installed alpha.105 direct device-control first answer, the native inventory and identity-matched device detail calls both succeeded. The source device detail described the target as currently allowed, no timer set, and advertised a native delay-based block command. The model unnecessarily drafted a helper variable creation with confirm=true; the existing prewrite proposal checkpoint intercepted it, recording an unsent proposal but executing no write. The next model round described the correct timed native command in prose and said to "please confirm". No native write tool was called, no UI approval was pending, and typing "proceed" as the next message could not confirm an expired action. An earlier source-discovery and relative-delay fix did not cover this last-mile proposal-to-UI handoff.

No historical chronology or reporter-versus-initiator causal attribution was requested in this action task; the original read receipts establish command availability, not scheduling or execution. No native tool error or device change was recorded.

## Bounded engineering correction

1. Detect a finished prose-only confirmation for a **direct imperative**, not a question, explicit read-only request, or a completed native write. Require a successful in-request identity-matched `hub_get_device` receipt with at least one advertised command, the current advertised writer name and a functioning web UI approval channel. Old chat, catalog names and broad inventories alone do not qualify.
2. Reuse one bounded model opportunity to choose (or decline) a native writer from the same receipts. This guidance does not select target/command, forge params, bypass prewrite reconsideration, pre-approve a device write, create a helper or infer the real-world effect. Ambiguous target, missing genuine permission, true state risk or unsupported semantics must remain blockers.
3. When a real native write is selected, its EXACT structured arguments must pass the existing active-request `Interaction.before_call` approval card; the user sees **Approve / Edit / Dry-run / Dismiss**. Numerical native command parameters are shown accurately as numeric parameters; never guess their unit in the client preview. The card displays a proposal, not an execution.
4. If the model still emits text-only confirmation and no native write attempt occurred, publish `action_selection.status=unprepared_confirmation` and private handoff telemetry. Show **Prepare action / Edit request / Dismiss** choices. A user clicking Prepare action or typing bare "proceed" in this specific unqueued state creates a NEW Ask requiring fresh model-selected evidence and the SAME UI approval. It cannot authorize an old/expired write or auto-replay an old tool call. No silent execution or unrelated automation creation.
5. Keep write failures, declined approvals, read-only requests and genuinely resolved actions outside the "unprepared" selector. All security, app permission, approval ID validation, provider routing, source receipt provenance and V1 isolation remain.

## Evidence and tests

Fictional offline scripted tests cover current original device-detail matching, malformed/missing/wrong device receipt rejection, offered tool and deadline gates, prewrite false-helper proposal, model-led recovery into an actual native command, an active UI approval future that prevents execution until approved, model refusal leaving selectable options but no writes, and no UI approval channel. An existing UI test confirms numeric native params appear in exact write approval, not free-text prose. No real hub or paid model called by tests.

Gate release on exact-head full Python, V2 container build/smoke, metadata, interface, snapshot, scorecard CI and post-merge checks. Installed acceptance: use a low-risk intended action, verify the UI presents actual selected command and parameter before approval, confirm once, inspect the original native receipt and source-derived readback, then verify the future timed outcome separately at/after the target time. Check decline path for no native write. Don't claim scheduling from a tool proposal alone. Roll back if direct action is executed without its explicit UI approval, ambiguous device targeting becomes automatic, or stale action replay is observed.
