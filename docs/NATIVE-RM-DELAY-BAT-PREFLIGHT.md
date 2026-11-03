# Native Rule Machine delay — read-only preflight and isolated MCP BAT

**2026-11-03 | Offline preparation only | HomeBrainOS v0.18.380 unchanged**

## Decision and evidence boundary

The upstream [MCP Rule Server issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) remains open for native `atDate#` fields. It blocks *dated one-time triggers*, not necessarily an existing Rule Machine delay action. The upstream `TOOL_GUIDE.md` documents `hub_set_rule(operation="create")` for a native Rule-5.1 child and `hub_call_rule(action="actions")` for the Run Actions button. However the writer's success on the installed server has NOT been tested.

Read-only HomeBrain v0.18.380 **already verified** existing manual rule 4259's ordered native methods `getDelay` (ID 1) then `getOnOffSwitch` (ID 2). Earlier independently typed saved fields showed `delayMinute.1=2`, `onOff.2=false`, and `onOffSwitch.2` pointing to the manually tested virtual device 7995. Hubitat reported an OFF command and OFF state attributed to the manual rule. These observations do NOT prove the entire parameter/trigger document, MCP-created rule lifecycle, Run Actions via MCP, an attributable pending job, reboot persistence, or Internet blocking.

**Important contract discovery:** The upstream tool guide uses **different hourly acknowledgements** for `hub_set_rule` (guide section `set_rule_reference`) versus `hub_call_rule` and `hub_set_rule_paused` (section `builtin_app_tools_rules`). The offline candidate previously obtained only the first. The new offline-only patch retrieves both and uses each with the corresponding call; it still has `NATIVE_DELAY_ENABLED=False` and no runtime import. A write-guidance key is *not* authorization to issue writes.

## Installed read-only settings/triggers checkpoint — 2026-11-03 16:12 UTC

The user submitted the full HomeBrain v0.18.380 answer and Technical details JSON for `hub_set_rule(operation="read",rule_id=4259,args={"sections":["settings","triggers"]})`. It reported `success=true`, `sourceSuccess=true`, `projectionVerified=true`, one nonmutating `typed_native_rule_section` receipt, **49 settings** (4 redacted or unsupported) and **zero returned trigger entries**. Request elapsed 2.397s; one MCP call 230 ms, zero model rounds. In the returned answer:

- `actType.1=delayActs`, `actSubType.1=getDelay`, `delayMinute.1=2`; `delayHour.1` and `delaySecond.1` are **blank** (not verified zero).
- `actType.2=switchActs`, `actSubType.2=getOnOffSwitch`, `onOff.2=false`, and `onOffSwitch.2.device_ids=["7995"]`. The capability setting's raw value was labelled unavailable; the device ID selector was still shown.
- `cancelAct.1`, `randomAct.1`, and `uVar.1` are **blank** (not verified false). The absence of returned trigger rows is consistent with the manually made triggerless test, but does not alone certify all Rule Machine execution semantics.
- The **technical receipt attests the section retrieval but does not embed individual setting rows or the raw trigger collection**. The readable values are from HomeBrain's returned textual projection. Do not treat `projectionVerified=true` as independent provenance for every setting value, or merge this read and the earlier actions read into a single atomic native snapshot.

This **closes the requested settings/triggers read checkpoint**, not the live MCP-created BAT. Existing offline candidate `verify_rule()` already requires exact readable numeric/Boolean settings for its **newly created** child. Extra synthetic negative controls ensure the manually observed blanks are **never silently accepted as 0/false**, and no `hub_call_rule` follows such a mismatch.

**Remaining preflight:** installed gateway contracts/version, typed native Rule Machine parent/type join, complete duplicate-rule inventory, authorized/MCP-owned virtual-switch inventory, and source-confirmed recent backup immediately before a separately approved write. Never rerun the manual Rule 4259 test to fill these gaps.

## Installed native-parent identity checkpoint — 2026-11-03 16:22 UTC

The user's v0.18.380 typed read-only Rule Machine inventory finished in **1.057s**, using **five tool calls**, with `metrics.outcome=unresolved` and no writes. The projection retained **candidate app 169** with `appTypeId=18`, but **no native Rule Machine app-type IDs** in the returned `hub_list_apps(scope="types")` evidence. The separate `hub_get_app_config(appId=169,summary=true)` lacked typed `appType.namespace/name`. The complete app/rule lists and zero exact `(One-time YYYY-MM-DD HH:MM)` suffix matches are not proof of the parent class or of no conflicting `HB delay | ...` rule. Specifically, the original user request also asked for `hub_list_devices(scope="owned",format="detailed")`, but the chosen native-rule inventory route **did not issue that tool call**, so **owned device inventory is NOT CHECKED** (not empty).

**Upstream explanation from current source** (`libraries/mcp-code-management-lib.groovy`): `hub_list_apps(scope="types")` starts with `/hub2/userAppTypes`, which lists community code definitions, and adds built-in classes from `/hub2/appsList.systemAppTypes` if that property is a usable list. A successful, count-complete response therefore need not contain the built-in class required to match `appTypeId=18`; a missing join remains unverified. The installed summary also does not expose a usable typed class. The current upstream dated-trigger [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) already describes this separate parent identity visibility gap. **Do not hardcode app 169, assume type 18 is definitely the native parent, use the legacy 19 class or issue any create operation on name-only evidence.**

**Conservative decision:** the candidate writer's strict `find_parent()` must refuse the current installed evidence (`rm_parent_type_mismatch`). Offline negative controls cover returned-list completeness without a native join and false/community namespace. The correctly unresolved outcome is not a Hubitat or MCP read outage. A safe isolated MCP-created BAT remains gated until parent identity can be source-proven, along with the remaining owned-device, fresh-backup and installed guide checks. If a read-only installed endpoint cannot prove the namespace/name, request a narrow upstream exposure of the parent class (or a verified alternative read); do not bypass the safety gate.

### Next read-only request — only the omitted owned-device inventory

```text
Read-only inventory of MCP-created virtual devices ONLY.

Call hub_list_devices with scope="owned" and format="detailed" through
an authorized read-only MCP gateway. Follow every returned nextCursor.
Return the number of returned devices and the completeness status.
For each Virtual Switch report its device ID, label, driverType,
driverNamespace and mcpManaged flag when source-provided.

If the source read fails, is partial or is unavailable, report the exact
MCP error and do not infer an empty inventory.

Do not use any rule operations or modify any device, rule, backup or setting.
```

Keep the returned Technical details JSON private; do not commit raw household inventory. **This does not itself resolve the native Rule Machine parent identity gap.**

## Read-only preflight — collect before asking for any mutation approval

1. **Installed source contract:** Read `hub_get_tool_guide(section="set_rule_reference")`, `hub_get_tool_guide(section="builtin_app_tools_rules")`, and `hub_get_tool_guide(section="virtual_devices")`; inspect actual available gateway/sub-tool schemas and installed MCP version. Guide hashes are rotating; fetch new keys when/if a separately approved write later happens. Do not call `hub_set_rule(operation="form")` — even opening the native editor may run app code or change state.
2. **Full existing manual rule representation:** One read-only `hub_set_rule(operation="read",rule_id=4259,args={"sections":["settings","triggers"]})`. The actions-only read is already verified; no repeat required. Check native field names/types for delay, OFF and device selector, trigger absence, completeness/page cursor and native target identity. Never infer that missing fields are disabled or a zero trigger count when the section is absent.
3. **Identity and inventory:** Enumerate exact native Rule Machine parent instance **and matching built-in type** with complete cursor handling; enumerate exact-name matching rules and check ambiguity. Neither an untyped app ID nor a shortened inventory proves uniqueness. Confirm whether the installed version's read-only `hub_list_rules` and `hub_list_apps` expose full usable data.
4. **Device/backup:** Read `hub_list_devices(scope="owned")` and `hub_list_backups(scope="hub_local")` for MCP-owned virtual targets and backup recency. Do not infer a manually created Hubitat virtual switch is MCP-owned. A backup younger than 24 hours must be **source-confirmed just before a future write**; do not create one during this preflight.
5. **Safety/permission:** Confirm read-only tool availability, rule creation guidance, no conflicting existing test rule, target scope, and no hidden write calls. If a source errors, is truncated, or does not match, return **blocked / not yet established**, not permission to create.

Both the manual rule's **actions-only** read and its separate **settings/triggers** read have now been provided live. The installed guides, native parent/type join, complete relevant inventories and recent backup remain unverified. Public upstream source contracts are useful context, not proof of the user's installed gateway or Rule Machine capabilities.

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
