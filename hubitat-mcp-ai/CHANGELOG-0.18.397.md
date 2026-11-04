# HomeBrainOS 0.18.397 — evidence-first installed MCP Rule Server version gate

## First-attempt observed baseline

The user asked **"Block TV after 30 mins"** on HomeBrainOS **0.18.396**. The request correctly used the deterministic `unified-mcp-agent` scheduled-write route but returned unresolved in **121 ms**, with one successful `hub_get_tool_guide(section=set_rule_reference)` read, **zero device or rule writes**, and the unhelpful message `native_oneshot_date_field_unverified`. Their previously supplied MCP preflight identified an installed Rule Server **5.1.5**, but that was an earlier observation, not a fresh current-version read. The scheduling feature added upstream in issue [#575](https://github.com/kingpanther13/Hubitat-local-MCP-server/issues/575) requires **5.1.6 or newer**; do not bypass this hard safety gate on older servers.

## Source finding and change

Upstream `hubitat-mcp-server.groovy` implements `serverIdentity() = {name: "hubitat-mcp-rule-server", version: currentVersion()}` and `hub_get_info` returns `mcpServerVersion: currentVersion()`. HomeBrain previously checked only the cached `initialize.serverInfo` value when deciding whether a native, one-time dated Switch rule could be created. A cached or absent value and a genuinely outdated installation were collapsed into the same generic refusal.

When the cached identity is not already a supported version, HomeBrain now makes **one read-only `hub_get_info` call** and records its version, source and timing. It refuses with the **observed installed version** plus HPM update/reconnect guidance if below 5.1.6. If hub info reports 5.1.6+ while initialize is missing/stale, HomeBrain first refreshes initialize and requires the two identities to agree before any write can be queued. Missing, malformed, conflicting or failed reads remain fail-closed. An already verified initialize 5.1.6+ does not pay for an extra source call. A confirmed write rechecks this gate. Metrics now differentiate detecting a native contract from a truly incompatible version.

The previous "block TV after N mins" user workflow remains unchanged: resolve the unique Internet Switch from the Internet room, verify `off`, calculate a future Hubitat-local one-time date, prepare exactly one native Rule Machine `create` proposal, ask for confirmation, verify the native create receipt, and let the existing scheduled `HB one-shot |` cleanup delete expired owned rules. No cumulative-allowance app and no direct device command are added.

## Test and rollback

Offline regression cases cover 5.1.6 fast success, installed 5.1.5 source-confirmed rejection, stale 5.1.5 initialize refreshed to source-confirmed 5.1.6, mismatched identities, invalid/failed source results, the exact 30-minute prompt, and confirmation-replay refusal. Existing native creation/cleanup tests remain required CI gates. Production first-attempt outcome on the installed Hubitat server, real rule triggering, router reachability and any quality-rate change are **NOT MEASURED** pending a fresh user-supplied read/confirmation.

**No live Hubitat, Home Assistant or router state is modified by this PR.** If the server really is on 5.1.5, installing HomeBrain 0.18.397 alone cannot make dated rules possible: update the MCP Rule Server through Hubitat Package Manager to 5.1.6+ and reconnect. If read-only version handling regresses, revert this module change and fall back to 0.18.396's strict refusal.
