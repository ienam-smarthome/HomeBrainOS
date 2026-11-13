# HomeBrainOS v2 alpha.72 — rollback to working alpha.65

**Date:** 13 November 2026. **Reason:** restore previously working native delayed network blocking/scheduling while removing later experimental controller-discovery, action-continuation and receipt-guard regressions.

## Original working baseline

**Baseline commit:** `81a81df6225b01bb313ed127c52b9ccf9e2d47a4` (`2.0.0-alpha.65`, merged PR #1618). In the previous **source-real** Google TV live acceptance, the model selected the native Cudy-managed target's `blockInMinutes(2)` command. The timed block and subsequent block events were verified from native and recorder evidence. This is a verified historical result for that test, not a new alpha.72 live validation.

The native Cudy Managed Device driver already advertises immediate allow/block and delayed **block** (`blockInMinutes`), as seen in original Hubitat MCP receipts. This does **not** prove it supports delayed **unblock**: `allowForMinutes` starts access immediately for a limited duration, rather than unblocking *after* a requested delay. No unverified Rule Machine one-time automation is added to compensate for that gap.

## Exactly what this rollback does

- Restores **all eleven** V2 app, UI, skill, version-bearing test and ordinary test files that changed since alpha.65 to their original alpha.65 blob bytes, before applying the five necessary packaging version substitutions.
- Removes the six **V2-only** source/test modules first introduced in alpha.66–71: the experimental source-review extensions, action continuation, writer feasibility, receipt classifier and their new synthetic tests. Existing alpha.65 model-led native command execution and its native action/outcome review remain intact.
- Does **not** alter the upstream Hubitat MCP server, Cudy router rules, Hubitat automations, V1, HA, or the separate external Hub & Device Monitor.
- Preserves later historical design notes under `docs/` for reference, but labels them superseded by this rollback in the current status.
- Uses **`2.0.0-alpha.72`** as the released add-on version to allow the installed `alpha.71` addon to **upgrade** instead of requiring a HA Supervisor downgrade/reinstall. `alpha.72` is deliberately alpha.65 functional code, **not** the alpha.71 continuation with patches reapplied.

## Known limitations

- Delayed **block** was successfully observed in an earlier source-real test; alpha.72 is not yet independently live-tested after reinstall.
- Delayed **unblock** is **not** implemented by this revert. A direct immediate allow command is supported by the advertised driver, but scheduling the start of a later allow still needs a separately verified implementation. Do not claim native delayed unblock exists.
- A complex natural-language operation may still need a genuine clarification if this restored model chooses the wrong controller; we have not guaranteed every first answer.
- CI validation is about code/runtime regressions; it cannot establish the current live internet policy or act on the user’s devices.

## Acceptance gates

1. Validate that branch V2 runtime/skills/UI and non-version-bearing tests match baseline `81a81df` blob-for-blob; version-bearing files differ **only** from `alpha.65` to `alpha.72`.
2. Green exact PR-head v2 pilot suite, add-on container checks, full Python release assurance, repository validation.
3. Squash merge rollback PR, re-check merged head and all push workflows.
4. After installing alpha.72, test **one authorized delayed block** on an appropriate device, verify the native `blockInMinutes` receipt and delayed state using original MCP receipts, and only then describe installed behavior as confirmed. Delayed unblock is a separate optional future task.

**No real device action is performed by the rollback PR.**
