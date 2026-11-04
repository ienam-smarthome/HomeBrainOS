# Native one-time Internet-block rule — developer fix acceptance and safe BAT

## Installed v0.18.388 three-source preflight PASSED — offline BAT naming alignment

Source-supplied MCP Rule Server **5.1.5**; 21 hub-local backups with
newest source timestamp **2026-11-03 17:37:05 UTC**; both
`set_rule_reference` and `builtin_app_tools_rules` guide sections
readable. The actual test response returned
`preflightEvidenceComplete=true`, `readinessForMutation=false`,
4.463-second wall-time and zero model rounds. No writes or router
reads. Backup age was ~6h59m at the collector timestamp, but the
hub's own clock was not independently checked.

The offline dated BAT candidate previously generated a name without
the exact terminal suffix recognised by the maintained live inventory
reader. To avoid leaving an eventual disposable test rule
undiscoverable during source-scoped audit, the candidate now adds
`(One-time YYYY-MM-DD HH:MM)` at the end, in hub-local time, while
preserving UTC time plus a unique digest. Synthetic cross-module
tests verify the inventory would recognise the new format and not
the old one. This is **not** an automatic cleanup mechanism or
evidence that a real rule exists.

**Safety gates remain unchanged:** BAT writer disabled, no live
switch, rule, backup, HA/Hubitat or OpenWrt changes. Do not reuse
the existing MCP-owned household switch. Obtain independent hub
clock/backup verification and specific user approval for a new
disposable target, an ON state and one native dated OFF rule.
Verify scheduled job/readback and actual future OFF separately.
No production Internet-block enablement from this preflight alone.


**Date:** 2026-11-03 | **Production:** DISABLED | **No live Hubitat/HA writes performed**

## New multi-source read-only readiness route — v0.18.388 candidate

A fresh user result on v0.18.387 repeated native parent inventory,
rather than checking the separately requested installed MCP server
version, newest hub-local backup and tool-guide availability. The
technical receipt contained **no** `hub_list_backups`,
`hub_get_tool_guide`, or server-version projection; its prompt hash
differed from the earlier parent-inventory prompt. The installed
Rule Machine parent **remains verified**, but the readiness checks
have **not** been performed.

The v0.18.388 route is a **positive multi-objective read-only check**:
source serverInfo from MCP initialize, a single
`hub_list_backups(scope=hub_local)` read and the two guide sections
`set_rule_reference` and `builtin_app_tools_rules`.
No rotating guide-acknowledgement token, source filenames, raw backup
payload or private configuration is published. Missing version,
partial backups, unreadable timestamps or missing guide sections
remain explicitly unverified. It does not create a backup or authorize
a rule, switch, scheduled job, or router action.

**Source gates for the later disposable BAT remain separate:** current
hub backup freshness evaluated against independently observed hub time,
native date write/readback, pending scheduled job, timed OFF evidence,
non-reuse of existing MCP-owned switch and explicit user consent.
Both offline native-rule writer scripts remain disabled.

## Installed HomeBrain v0.18.387 identity acceptance — VERIFIED (2026-11-04)

The user supplied an exact same-question, read-only response:
`parents=[{appId:"169",appTypeId:"18",namespace:"hubitat",
proof:"source-typed-installed-app-summary"}]`,
`summarySourceChecks.typeProofGap=null`,
`catalogClassConflicts=[]`,
`parentIdentityComplete=true`, and `oneTimeMatchCount=0`
from complete current rule/app lists. It took 2.940s with no model
rounds, five local/remote receipts and no write. The native *parent
identity* gate is now **passed for this observed installed snapshot**.
The installed software version is self-reported; deployed Git SHA
is not independently authenticated.

The exact-name absence establishes **no matching suffix now**, not
a proof that no timed/recurring native rules exist or that one-shot
scheduling and automatic cleanup work. No native dated rule has been
created by HomeBrain. Do not infer BAT or real Internet-blocker success
from an inventory check.

**Next offline/read-only prerequisites:** current MCP Rule Server version,
recent hub-local backup timestamp and current native rule guide
availability. Source-reported version, not assumption from an upstream
release or the 36-tool UI label. The previously verified **one existing
MCP-owned Virtual Switch is not a new disposable switch and must not be
repurposed**. Any newly created test switch, ON command or dated rule
requires the user's separate explicit approval; no router changes.
Both BAT scripts remain default-disabled. See the top of
`docs/ANSWER-QUALITY-STATUS.md` for a single scoped read-only prompt.

## Developer fix is real — installed compatibility not yet verified

- [Upstream PR #576](https://github.com/kingpanther13/Hubitat-local-MCP-server/pull/576) was merged and released as **MCP server v5.1.5**. It closes [issue #575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575).
- `hub_set_rule` accepts a native Rule Machine `date` field because it validates the type declared by the page. `atDate#` must be a valid `yyyy-MM-dd` string. The developer reports a successful C-8/C-7 live test of a one-time dated trigger on firmware 2.5.2.135. This is **upstream** live acceptance, not a test of the user's installed C-8 Pro.
- `hub_get_app_config(appId=...,summary=true)` now includes an independently source-observed **namespace** from the native installed app, while `type` still holds its class name. Full configuration reads also contain `app.appType.namespace/name`, but render a page and can run page code. Prefer the cheap **summary read**.
- Built-in Rule Machine type rows may still be omitted from `hub_list_apps(scope="types")`. The disabled offline `find_parent` now accepts a **strict exact installed-app summary fallback** only when there is no matching type row, and otherwise refuses inconsistent/missing evidence. A name-only candidate or mere label/type ID is not enough.
- **Do not assume the user's installed MCP version:** the user says their server was updated, but no authoritative installed v5.1.5 receipt or fresh source-typed Rule Machine summary has been supplied yet. MCP v5.1.5 fixes two previously established blockers, not every scheduling, ownership, execution or cleanup gap.

## v0.18.387 native class namespace-absence distinction — GREEN MERGED

[PR #1373](https://github.com/ienam-smarthome/HomeBrainOS/pull/1373)
merged at `2cf6399b090919aa51b3656748fe3385c82a0d7a`
with 8/8 green CI and 6,212 Python tests passed. Both the maintained
read-only inventory projector and the **disabled offline** BAT parent
helper distinguish missing built-in namespace from explicit
contradictions. This does not verify the installed native parent,
MCP-server version, trigger firing or network enforcement. New evidence
must come from the next exact read-only HomeBrain question after
installing the add-on. Never silently enable a writer or use an
unverified rule as a household Internet block.

Upstream `hub_list_apps(scope=types)` can return `systemAppTypes` with
`system/isBuiltIn=true` but **no namespace**; that absence is not a
contradiction of the installed-app summary's independent
`getAppByAppId(...).appType.namespace` value. A catalog row with a
genuinely different namespace, name or explicit user-code flags remains
a veto. Public conflict witnesses are bounded/redacted and no new
MCP calls, writer permissions or BAT enablement have been added.
The v0.18.386 installed 3.611s read was source-incomplete for parent
verification; it did not expose the raw catalog class. v0.18.387
requires a fresh read-only installed acceptance before any BAT approval.

## Read-only inventory source selection — v0.18.386 GREEN MERGED

[PR #1371](https://github.com/ienam-smarthome/HomeBrainOS/pull/1371)
merged with 7/7 CI green and 6,197 Python tests passing. This confirms
**offline source routing correctness**, not installed MCP version,
native Rule Machine identity, dated trigger firing or Internet-blocker
function. A fresh installed read-only receipt remains mandatory.
No test switch or rule has been created by repository work.

## Read-only inventory source selection — v0.18.386 original candidate

The first installed v0.18.385 identity/inventory attempt did **not** take
the intended thin summary path. The original question's "explain why
identity remains unverified" was incorrectly classed as a historical
causal investigation. Its six model rounds and Groovy source reads
did not independently prove the native namespace; it also conflated
an all-rule count with one-time rule matches.

v0.18.386 corrects the **objective classifier**, not the MCP writer:
a plain source-coverage explanation is an inventory read; execution
causes and actual rule behavior still require deeper evidence. On
a missing native type-list join, the pre-existing inventory route can
call only `hub_get_app_config(appId=<verified candidate>,summary=true)`,
whose flat `namespace` is understood since v0.18.385. It does not
read built-in source code, add a model round or create any rules.
Before commissioning a BAT, require a current exact source receipt
and separate approval for the one disposable test switch/rule.

## HomeBrain v0.18.385 read-only identity compatibility (candidate)

After MCP 5.1.5, the thin `hub_get_app_config(appId,summary=true)`
exposes native `namespace` directly alongside `id`, `type`, and
`user`; it is not required to include the **full-page**
`app.appType` object. HomeBrain 0.18.384 still required that nested
object in its inventory projector, so a valid new upstream summary
could be incorrectly reported as an unresolved parent. HomeBrain's
0.18.385 candidate accepts only source-verified **flat** class identity,
retaining the older nested form and strict contradictions/ID checks.
The test is read-only, without opening a Hubitat app form. This repairs
identity interpretation; it does **not** authorize a dated write or
prove the installed hub/server has the expected readback.

## Architecture decision

**Prefer a single dated native trigger over the old triggerless Delay → Run Actions workaround.** The dated rule is created with one trigger of `Certain Time (and optional date)` and one OFF action, and its future native schedule should run without an immediate `hub_call_rule(action="actions")`. The old script `scripts/native_rule_delay_candidate.py` remains disabled and retained as historical fallback only. New script `scripts/native_rule_dated_candidate.py` is also **OFFLINE ONLY** with `NATIVE_DATED_ENABLED=False`, no add-on runtime import and no production flag.

Proposed source-shaped creation (for **one separately approved disposable MCP-owned Virtual Switch**, not an Internet-blocked device):
```json
{
  "operation": "create",
  "confirm": true,
  "args": {
    "parent_id": "<source-verified native Rule Machine parent>",
    "name": "<unique BAT-specific label>",
    "changes": [
      {
        "part": "trigger",
        "value": {
          "capability": "Certain Time (and optional date)",
          "fields": [
            {"name": "time#", "type": "enum", "value": "A specific time"},
            {"name": "atTime#", "type": "time", "value": "<hub-local ISO with offset>"},
            {"name": "date#", "type": "bool", "value": true},
            {"name": "year#", "type": "bool", "value": false},
            {"name": "atDate#", "type": "date", "value": "<yyyy-MM-dd>"}
          ]
        }
      },
      {
        "part": "action",
        "value": {
          "type": "switchActs",
          "subtype": "getOnOffSwitch",
          "fields": [
            {"name": "onOffSwitch.#", "type": "capability.switch", "value": ["<new test switch ID>"]},
            {"name": "onOff.#", "type": "bool", "value": false}
          ]
        }
      }
    ]
  }
}
```

This is a **candidate** based on upstream typed example, not a claim that exact rule trigger/readback shape has passed on the user's hub. Native `year#` exposure and trigger `capabstrue` representation must be validated in the harmless BAT; do not silently drop fields or accept an approximate date. Times use the hub's configured local timezone, offset-aware; handle BST/GMT and rounded-minute scheduling without requesting an earlier time. A timed OFF on a virtual switch proves only Hubitat's reported switch transition, **not** an OpenWrt firewall or real Internet block.

## Authorization and safety gates

- No unattended jobs; no production writer integration yet. Both script gates default disabled.
- A future BAT needs **separate explicit user approval** for: creating **one newly owned disposable Virtual Switch**, setting it **ON**, creating **one** native dated Rule-5.1 under a source-verified parent, and monitoring its OFF report; **no router/firewall changes and no production target**. Confirm current hub backup before any write; the new candidate refuses stale/missing backups instead of creating one.
- Use newly refreshed `hub_get_tool_guide(section="set_rule_reference")` and `hub_get_tool_guide(section="builtin_app_tools_rules")` acknowledgements for exactly the corresponding operations. These keys are necessary tool protocol fields, not user consent.
- Enforce a single intended rule label, no duplicate existing rule, create **once**. A timed-out create is an unknown outcome; **never blindly retry**.
- Require complete native readback of rule ID, action order, exact target ID, `date`, `time`, `date=true`, trigger capability and healthy rule status. Missing or blank fields = unverified. Require a source-reported pending `scheduledJobs` entry, but **this alone does not prove its due/trigger or future physical effect**.
- On a confirmed ID with partial/invalid document, pause only that newly created disposable rule; do not delete it or touch other rules. Refuse on ambiguous create outcome.
- Never call `Run Actions` for a dated BAT: that would operate the switch **immediately**, defeating the test. Do not automatically clean up, reboot or delete without separately scoped approval and independent completion/ownership evidence.
- Production design additionally needs durable ownership records, duplicate/restart/reboot behavior, source-timed execution evidence, cleanup permissions and safe mapping of virtual commands to an actual Internet block. A switch OFF report is not proof that the device lost Internet access.

## Next **single read-only** installed-version/identity acceptance

Use the existing HomeBrain UI in **New topic** on Free. Ask:

```text
Read-only MCP native Rule Machine compatibility check.

Call hub_get_app_config(appId=169, summary=true) using the authorized
read-only MCP gateway. Return only success, id, type, namespace, user,
appTypeId (if present) and the exact source error if any. Do not infer
missing fields or call a form operation.

If the MCP server's own version is available from an existing read-only
status tool, report the self-reported version and tool name, otherwise state
"installed MCP version not independently verified".

Do not create, execute, modify or delete any rule, device or backup.
```

Return **the full answer and Technical details JSON**, with private credentials omitted. This check avoids repeating previously completed Rule 4259 and owned-device reads, and does not alter anything. A summary reporting type `Rule Machine` and namespace `hubitat` must still be cross-checked with app instance identity and explicit scope before a write. A verified upstream release is *not* authority to change the live network.

## Test evidence / handoff

- Synthetic tests of native typed date, readback refusal, strict parent summary, backup freshness, duplicate creation, unknown create result and no Run Actions run entirely offline.
- **No installed native dated-rule create**, schedule-at-date, automatic expiry, cleanup/reboot or OpenWrt block has been tested by this change.
- Do not describe the production Internet-blocker as enabled or finished. Keep the broader HomeBrain Answer Quality charter active; this resumed capability work is isolated and must not replace measured Q1/Q2 development.
