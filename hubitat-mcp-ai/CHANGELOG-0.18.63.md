# HomeBrainOS v0.18.63 — Native Rule Machine write intent and staging safety

## Live regression: v0.18.62
On 2026-10-22 the user issued an explicit creation request for a Rule Machine TEST rule affecting Livingroom Light 1 (7805) using FP400 motion (7978), 23:00–06:00, ten minutes uninterrupted inactivity. The instruction required the rule to be **disabled from the outset**, forbade create-active-then-disable, required exact schema verification and confirmation, and prohibited changing existing app 4019.

The add-on reported success=true / outcome=success / request_class=write, but actually made only four read calls (hub_list_apps, set_rule_reference guide, get_device 7805 and 7978), blocked three write proposals, queued no confirmation, and returned the generic UNVERIFIED_MUTATION_REFUSAL. Eight free Gemma rounds consumed 81.4 seconds provider time and 94.1 seconds total. No successful Hubitat write receipt exists.

## Corrections
- Explicit positive authorisation for creation with confirmation outranks a general task planner model's advisory classification as operation=propose. Read-only design requests still remain proposal-only and the native confirmation/write policy remains mandatory. A model cannot grant permission the user did not give.
- Add a deterministic *atomic disabled-from-birth preflight* for explicitly authorised native Rule Machine creations that demand disabled-at-creation or explicitly prohibit an active rule between create and disable. The documented native hub_set_rule create path has no independently verified atomic disabled-at-create contract. Fail closed before any model loop or Hubitat write/confirmation; do not substitute a two-step create active -> disable sequence.
- Replace generic unverified-write success narration with an actionable no-write outcome. A write-classified request with a blocked creation or blocked model proposals and no confirmed write/approval must report outcome=unresolved, API success=false and status_verification=no-write-performed, not a green Success badge. Preserve read receipts and distinguish blocked proposal from an attempted Hubitat command.
- Do not treat successful tool **reads** as evidence that a rule was created.

## Tests
- Reproduce the authorised disabled-first exact sensor/light/night-time test without any model rounds or native calls.
- Pure read-only design requests and ordinary authoring requests must not trigger the disabled-first boundary.
- Original three blocked proposals and a stale success classification must render as unresolved and false; a valid pending confirmation must not be marked failed.
- Ensure advisory proposal planning cannot revoke user write authority, without bypassing native tool confirmation or safety policy.

## Remaining capability gap
To really test creating a disabled Rule Machine rule, obtain authoritative installed native gateway documentation proving disabled-at-create is *atomic*. The currently described hub_set_rule create grammar accepts a name and trigger/action shortcuts but does not provide a verified inert-at-create option. Do not create an incomplete/active automation or silently change app 4019. A separate user-authorised workflow may be possible after safe native staging support is implemented and demonstrated.

No live Hubitat modifications made by this repository change.
