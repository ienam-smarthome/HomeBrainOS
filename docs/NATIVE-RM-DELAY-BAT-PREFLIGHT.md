# Native Rule Machine delay — read-only preflight and isolated MCP BAT

**2026-11-03 | Offline preparation only | HomeBrainOS v0.18.380 unchanged**

## Decision and evidence boundary

The upstream [MCP Rule Server issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) remains open for native `atDate#` fields. It blocks *dated one-time triggers*, not necessarily an existing Rule Machine delay action. The upstream `TOOL_GUIDE.md` documents `hub_set_rule(operation="create")` for a native Rule-5.1 child and `hub_call_rule(action="actions")` for the Run Actions button. However the writer's success on the installed server has NOT been tested.

Read-only HomeBrain v0.18.380 **already verified** existing manual rule 4259's ordered native methods `getDelay` (ID 1) then `getOnOffSwitch` (ID 2). Earlier independently typed saved fields showed `delayMinute.1=2`, `onOff.2=false`, and `onOffSwitch.2` pointing to the manually tested virtual device 7995. Hubitat reported an OFF command and OFF state attributed to the manual rule. These observations do NOT prove the entire parameter/trigger document, MCP-created rule lifecycle, Run Actions via MCP, an attributable pending job, reboot persistence, or Internet blocking.

**Important contract discovery:** The upstream tool guide uses **different hourly acknowledgements** for `hub_set_rule` (guide section `set_rule_reference`) versus `hub_call_rule` and `hub_set_rule_paused` (section `builtin_app_tools_rules`). The offline candidate previously obtained only the first. The new offline-only patch retrieves both and uses each with the corresponding call; it still has `NATIVE_DELAY_ENABLED=False` and no runtime import. A write-guidance key is *not* authorization to issue writes.

## Read-only preflight — collect before asking for any mutation approval

1. **Installed source contract:** Read `hub_get_tool_guide(section="set_rule_reference")`, `hub_get_tool_guide(section="builtin_app_tools_rules")`, and `hub_get_tool_guide(section="virtual_devices")`; inspect actual available gateway/sub-tool schemas and installed MCP version. Guide hashes are rotating; fetch new keys when/if a separately approved write later happens. Do not call `hub_set_rule(operation="form")` — even opening the native editor may run app code or change state.
2. **Full existing manual rule representation:** One read-only `hub_set_rule(operation="read",rule_id=4259,args={"sections":["settings","triggers"]})`. The actions-only read is already verified; no repeat required. Check native field names/types for delay, OFF and device selector, trigger absence, completeness/page cursor and native target identity. Never infer that missing fields are disabled or a zero trigger count when the section is absent.
3. **Identity and inventory:** Enumerate exact native Rule Machine parent instance **and matching built-in type** with complete cursor handling; enumerate exact-name matching rules and check ambiguity. Neither an untyped app ID nor a shortened inventory proves uniqueness. Confirm whether the installed version's read-only `hub_list_rules` and `hub_list_apps` expose full usable data.
4. **Device/backup:** Read `hub_list_devices(scope="owned")` and `hub_list_backups(scope="hub_local")` for MCP-owned virtual targets and backup recency. Do not infer a manually created Hubitat virtual switch is MCP-owned. A backup younger than 24 hours must be **source-confirmed just before a future write**; do not create one during this preflight.
5. **Safety/permission:** Confirm read-only tool availability, rule creation guidance, no conflicting existing test rule, target scope, and no hidden write calls. If a source errors, is truncated, or does not match, return **blocked / not yet established**, not permission to create.

Only the existing rule's **actions** read has been provided live in this conversation. The remaining live preflight inputs are **not yet collected**. Public upstream source contracts are useful context, not proof of the user's installed gateway or Rule Machine capabilities.

### One copyable HomeBrain read-only request (no mutations)

```text
Read existing Rule Machine rule 4259 using hub_set_rule with
operation="read", rule_id=4259,
args={"sections":["settings","triggers"]}.

Return the saved native settings relevant to Delay action 1 and OFF action 2,
the trigger section and its count, and any missing or unsupported fields.
Include the actual source status and error code if a read fails.

Strictly read-only. Do not use operation="form". Do not create, update, run,
pause, delete, trigger, create a backup or change any device or rule.
```

Send HomeBrain's **whole answer and Technical details JSON**, not a screenshot alone. Secrets/raw private exports must remain out of public GitHub PRs.

## Proposed isolated MCP-created virtual-switch BAT — requires separate explicit approval

**Scope:** one fresh MCP-owned **Virtual Switch** with a unique BAT-only label and newly confirmed device ID, one newly created triggerless **Rule-5.1** child with two actions, a **120-second delay followed by OFF**. Absolutely no Cudy router controls, real Internet-block targets, firewall, Hubitat production device or existing rule 4259 is to be written.

Ordered runbook after the user approves that precise test:

1. Re-read installed guide keys and device inventory, verify a current hub backup and the single typed Rule Machine parent; reject duplicates, unknown state, missing authorization or unsupported action fields. Record the unique intended BAT label and approval in a local audit receipt; no broad write approval.
2. Create **one** MCP-owned test Virtual Switch. Verify the returned device ID/driver/label and that it is a switch. A partial or timed-out create is **ambiguous**: inspect read-only inventory; **never retry blindly**.
3. Set this test switch **ON exactly once**, verify ON state, and record the time and provenance. Without a confirmed starting ON, a later OFF is not a meaningful transition test.
4. Create **one** triggerless native child with exactly two native actions and no other actions/conditions. Confirm the returned app ID, linked parent, healthy/not-broken state and source-matched exact settings, triggers and action order. A partial create or timeout must not be retried automatically or started.
5. Invoke `hub_call_rule(action="actions")` **once** for that exact new rule, using its **own** `builtin_app_tools_rules` acknowledgement. Record the response and start time. A non-success or timeout is not proof that nothing ran; **do not retry**.
6. If available, inspect independently attributed pending schedule/job data while the two-minute delay is active. A bare `scheduledJobCount>0` is not sufficient attribution. Then check a source-recorded OFF command **and** OFF state for the new test virtual switch after the delay. Establish only reported switching, never physical Internet access.
7. Never reboot, delete, repeat Run Actions or perform automated cleanup without another explicitly scoped approval. Failed/uncertain tests leave a clearly labelled child/switch for read-only inspection and manual cleanup planning; do not silently substitute an existing device.

**BAT pass criteria:** exact new native rule and target identities; complete matching readback and trigger absence; one successful MCP Run Actions result; source-timed ON→OFF report plus attributable command after the intended delay; no unintended device writes; no duplicate starts. Pending-job provenance must be reported separately as verified/unverified. Reboot persistence, cleanup and actual timed Internet-block behavior are **not tested by this BAT**.

## Rollback / release gate

This audit is **offline-only** and does not enable or import `scripts/native_rule_delay_candidate.py` into the Home Assistant add-on. No configuration flags, rule/device state, scheduler registrations, or app version change. The candidate's safety gates stay disabled. Revert the offline script/tests/docs to restore the previous preparation state. The permanent Answer Quality roadmap (Q1/Q2 benchmark next) remains intact; the virtual-switch BAT is a separate explicitly approved capability validation task.
