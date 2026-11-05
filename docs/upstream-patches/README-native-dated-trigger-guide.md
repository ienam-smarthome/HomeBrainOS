# Upstream MCP Rule Server v5.1.6 native date-trigger guide patch

**Status:** Draft contribution prepared in HomeBrainOS; **not submitted or merged upstream**. The connected GitHub account has `pull=true` and `push=false` for `kingpanther13/Hubitat-local-MCP-server`, no connected fork. A previous issue-create attempt returned HTTP 403. Do not interpret the local patch or a HomeBrainOS docs PR as an upstream release.

## What is prepared

[Patch file](Hubitat-MCP-native-dated-trigger-guide-v5.1.6.patch), based on upstream main commit `1c01e0a5c9ed65414fba3e2eac83a2e9861433ba` (upstream v5.1.6, 4 Nov 2026).

It touches three upstream files:

1. `libraries/mcp-native-documents-lib.groovy` — extends the **served** `set_rule_reference` guide with a known Rule Machine 5.1 `Certain Time (and optional date)` typed field example (`time#=enum`, `atTime#=time`, `date#=bool`, `atDate#=date`), with date value `yyyy-MM-dd` and a native timestamp example for `atTime#`.
2. `TOOL_GUIDE.md` — the matching **generated** static reference. For future updates regenerate with `python tools/build-tool-guide.py` rather than editing it by hand.
3. `src/test/groovy/server/ToolGuideSubSectionsSpec.groovy` — Spock regression requiring the served guide to include the field names/types and **not** represent a guide example as live schedule verification.

This is a **static documentation/example improvement** grounded in the upstream PR #576 / issue #575 date-input regression and its tests. It does **not** read an installed native page, create a rule or prove one-time runtime firing. Native page conditions (including `year#`) must be independently verified on the target Hubitat firmware.

## Apply to an upstream fork

Use a personal fork of [the upstream repository](https://github.com/kingpanther13/Hubitat-local-MCP-server), based on main at or compatible with the above commit. From a working clone:

```bash
git switch -c docs/native-rule-dated-trigger-guide
git apply --check /path/to/Hubitat-MCP-native-dated-trigger-guide-v5.1.6.patch
git apply /path/to/Hubitat-MCP-native-dated-trigger-guide-v5.1.6.patch
python tools/build-tool-guide.py --check
./gradlew test --tests 'server.ToolGuideSubSectionsSpec'
python tests/sandbox_lint.py
./gradlew test
```

Before submitting to upstream, follow `AGENTS.md` in that repository. In particular, the public served guide must **not** include issue/PR references (this draft complies), and the upstream policy calls for an end-to-end test against its dedicated CI test hub for any observable tool result. **An E2E assertion in `tests/e2e_test.py` and upstream CI have not been completed** because the fork/PR could not be created here. Do not run their e2e suite against a personal hub.

The patch was checked against the upstream three source locations and successfully `git apply --check`ed on exact-context synthetic fixtures. It has **not** been validated in a full upstream clone or with the Groovy/Hubitat CI environment.

## HomeBrainOS status

Installed HomeBrainOS v0.18.423 at 20:11 UTC on 5 Nov 2026 showed `nativeGuideContract.inspectionStatus=checked`, but no `atDate#` documentation in the installed MCP 5.1.6 guide. Its overall `Unresolved` classification and `readinessForMutation=false` were correct. HomeBrainOS requires no version bump or native writer permission change for this documentation-only upstream preparation.

Next action requires a GitHub fork with push access (or an upstream maintainer), then a CI-tested upstream PR. Only after installing an upstream release that serves the new guide should HomeBrainOS repeat a **single** read-only preflight and assess the remaining native one-shot creation/activation safety contract. 
