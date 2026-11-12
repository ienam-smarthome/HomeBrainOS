# V2 daily-use control: delegated delayed device commands

**Decision date:** 12 November 2026. **Repository baseline:** V2 `2.0.0-alpha.63` on `main` (PR #1615). **Status:** source/code contract reviewed; synthetic regression only; no live hub/router writes, no installed first-answer acceptance.

## Decision

For a one-off relative delay (e.g. "disconnect this device in N minutes"), **prefer the target device's advertised delayed command** if the connected Hubitat MCP server exposes it. Do not build a HomeBrain scheduler or create a native Rule Machine child solely to reproduce a device-driver timer. This is a general device-command decision, **not** a hard-coded media-device routing rule.

The current V2 model-led path already has the necessary composition:

1. Resolve the user's requested target against fresh `hub_list_devices`; use `hub_get_device` for exact identity and `supportedCommands`. Do **not** infer that an ambiguous nickname matches an exact device. The upstream skill requires confirmation for a non-exact match.
2. Inspect the **live** native `hub_manage_devices` gateway/leaf contract (or the flat equivalent) and choose its advertised `hub_call_device_command` tool. Never guess a driver's internal command name from a human-readable Hubitat UI label.
3. Pass the validated `deviceId`, the driver-advertised command name and its typed arguments. The upstream MCP device-command contract specifies `parameters` as an array of strings; e.g. a discovered one-number command gets `["30"]`, not a new Rule Machine schedule. Respect the server Read/Write master and client-token permissions.
4. Treat a successful **command dispatch** as a request to the driver, not proof that the future internet block is already active, that the timer survived a hub reboot, or that the router has enforced a firewall rule. Query fresh device states that represent the pending deadline (if exposed). Report "scheduled, read-back verified" only when those states establish it; otherwise say "command accepted; pending deadline not verified".
5. For a cancellation, read the pending state and use only the driver's **advertised** cancellation command. Do not blindly retry a non-idempotent delayed command after transport timeout/outcome-unknown: first inspect the pending state/events.
6. At/after the deadline, distinguish driver-reported state from independently verified network enforcement. A pending deadline is not proof of blocking; an active block state alone does not prove all routes or existing network sessions were severed.

No background worker, cloud AI timer, database of pending jobs, special device-name patch, new MCP wrapper or host-owned scheduler should be added to V2 for the one-off case.

## Which scheduling surface?

| Intent | Preferred execution owner | Caution |
| --- | --- | --- |
| Block/disconnect after N minutes | Device's existing delayed-command timer, if advertised and supported | Fresh read-back of pending deadline; uncertain transport result must not be retried blindly |
| Allow temporarily for N minutes | Device's existing allow-for-duration command, if advertised | This may have different semantics from delayed blocking |
| Cancel the pending delay | Device's existing cancellation command, if advertised | Verify cleared pending state |
| Repeating daily allowed-hours window | Device's existing schedule-window preferences, if the driver supports them | First read the native preference contract; verify applicable timezone and overnight boundaries |
| Complex multi-device or conditional recurring policy | Native Hubitat automation, when its authoring contract is verified | Separate approval/backups and targeted acceptance; do not assume one-off dated RM authoring is verified |
| One-off fixed clock time but no driver capability | Explicitly investigate available native scheduling tools | Never silently fall back to an unverified dated Rule Machine rule |

## Existing code and upstream contracts reviewed

- `hubitat-mcp-ai-v2/rootfs/app/agent.py`: model-selected live catalog, optional gateway-leaf schema discovery, native `mcp.call`, original source receipts; no host scheduler.
- `hubitat-mcp-ai-v2/rootfs/app/mcp.py`: live schema argument validation, gateway call shape, no retry of uncertain `tools/call`.
- `hubitat-mcp-ai-v2/rootfs/app/interaction.py`: `confirm=true` path pauses for explicit approval. Routine device commands may **not** contain that flag, so this is not a general approval mechanism for every write; use only with an authorized user control request and exact target identity. Do not claim blanket confirmation enforcement.
- `hubitat-mcp-ai-v2/rootfs/app/skills/hubitat/SKILL.md`: fresh supportedCommands, exact-match identity, native device command and state readback.
- Upstream `kingpanther13/Hubitat-local-MCP-server` `TOOL_GUIDE.md` section `hub_call_device_command`: string `parameters`, `state` snapshot may lag, optional `waitFor`, uncertain `outcomeUnknown`, and `hub_admin_write_devices` permission.
- `docs/HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md`: V2 Gate C requires controlled, source-real device-write acceptance; native dated RM creation is not validated.

## Exact installed acceptance (not yet run)

Keep tests on a noncritical device; a real internet-blocking test may interrupt active streams. In a new V2 conversation, provide an **unambiguous, exact device label or ID** and instruct it to:

1. **Read only:** identify the device, return `supportedCommands`, live gateway leaf schema, current access status and any pending delay. Check whether the delayed command really exists, and whether native Write permission is available. Do not treat a screenshot's visible label as the machine command.
2. **After explicit approval:** schedule a short delay (e.g. two minutes), without a Rule Machine rule. The action should make exactly one native device command write; capture the original private Technical JSON.
3. **Immediately after:** read the pending-deadline and duration attributes. State whether the driver actually registered the delay. Check the Hubitat Scheduled Jobs view if evidence is ambiguous.
4. **After the delay:** verify the driver reports blocked, then independently inspect firewall/router enforcement where authorized. Check for unwanted early block, duplicate scheduled jobs and reliable unblock/cancellation.
5. **Cancellation regression:** arrange another short delay, cancel it via the discovered device command, and verify no pending block remains.
6. **Negative tests:** read-only MCP token, ambiguous nickname, unsupported command, failed dispatch and timeout/outcome-unknown must never be presented as "scheduled successfully" or be retried as a second write.

**Acceptance requires** original live receipts and observed post-action state, not just model prose or a green synthetic test. The test must also verify that the model does not create an RM rule or HomeBrain timer. Preserve private device IDs, IPs, MACs and tokens outside public GitHub.

## Alias and operational questions remaining

A short user nickname like "TV" may refer to multiple household entities. The first live test must use an exact label, or the user must confirm a generic user-managed alias; **no device-specific hard-coded alias** should be inserted in V2. Long-lived alias support should be evaluated only if ordinary natural-language device resolution demonstrably fails.

Driver timer persistence across reboot, exact command spelling/signature, and true router-enforcement outcome are **unknown** until observed on the installed system.

**Next project gate:** One approved, first-try source-real command-and-readback exercise with private Technical JSON. If an upstream tool or driver contract is missing, address that actual gap; do not add an alternate scheduling engine speculatively.
