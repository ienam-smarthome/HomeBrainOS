# v0.18.388 — source-typed multi-objective Rule Machine read-only preflight

## Real observed failure and scope

Installed HomeBrainOS 0.18.387 returned a **different prompt hash**
`d166f6d6f0b6542856b4a39c54f4289b8f2d77573a67151014dba1533399360b`
at 2026-11-04 00:19 UTC, but answered **Rule Machine inventory**
again: parent app 169 verified, no exact one-time suffix found, 2.970s,
five read/typed-projection receipts, zero model rounds, and **no**
MCP-server version, local-backup inventory or guide section reads.
The exact submitted prompt was not echoed by this technical JSON, so
we cannot assert its precise wording. The previous user-requested
preflight explicitly asked for all three prerequisites. A pure
classifier reproduction shows `backup inventory` combined with
`Rule Machine` and `which` accidentally satisfies the Rule Machine
*single-subject inventory* shortcut.

## General change

- Add a scoped, read-only **multi-source readiness** route recognizing
  at least two positively requested objectives among MCP server version,
  hub-local backup timestamp and native tool-guide availability; exclude
  negative "do not create/execute" instructions from positive matching.
- Invoke that route before the single-object inventory shortcut, and
  explicitly exclude the readiness objective from inventory classification.
- Read installed MCP server version only from MCP initialize
  `serverInfo.name=hubitat-mcp-rule-server`, not HomeBrain add-on
  version or Hubitat platform version.
- Use only existing read-only calls: `hub_read_apps_code ->
  hub_list_backups(scope=hub_local)` and two
  `hub_get_tool_guide(section=...)` calls.
- Validate source timestamp formats and guide availability, publishing
  **neither** guide acknowledgement tokens nor backup filenames/private
  data. Missing version, guide, backup or partial source gives explicit
  unverified status with source-scoped coverage.
- The new typed preflight evidence always carries
  `readinessForMutation=false`, even if all three read requests succeeded.
  A backup timestamp does not establish freshness without an independent
  current hub clock. No native date firing, cleanup or OpenWrt block
  inference is allowed.

## Evidence/measurement

**Before:** one real observed 2.970s response on installed v0.18.387
with 0/3 requested readiness categories covered, 5 logical tools,
0 model rounds. Independent first-attempt provenance remains false.
**After (before installation):** offline simulations check source
selection, strict tool allowlist, no model/write calls, missing-source
partial results, no guide-token/backup-filename leakage. Full CI
status recorded in the PR after runs complete. **Actual installed
after-result, latency and first-answer quality remain NOT MEASURED.**
No fake latency, quality or Internet-blocker operational claim.

## Safety, rollback and next checkpoint

No Hubitat/HA/OpenWrt device or automation changes. Both offline
dated/delay BAT writers remain disabled and unimported by the runtime.
An existing MCP-owned virtual switch must not be repurposed. Revert
this release if the read-only source contract is incompatible with
the installed MCP server.

After green CI merge and installation, repeat the single *read-only*
multi-source preflight question already recorded at the top of
`docs/ANSWER-QUALITY-STATUS.md`. Supply complete natural response and
technical JSON. Separate explicit user approval, new disposable test
device and pending-job/fired-event evidence are mandatory for any
subsequent BAT, never implied by this read-only check.
