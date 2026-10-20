# HomeBrainOS v0.18.45 — Keep compound Internet requests out of immediate device control

## Live regression (v0.18.44)
The Free Gemma request `block Google TV (6923) if TV (4221) has been on for a total of 1 hour. Restart timer once Google TV has been unblocked` returned `Unresolved` in 49 ms with no model rounds. The immediate Internet parser wrongly treated the **entire conditional instruction** as a single target name and attempted an Internet-room fuzzy lookup of that text. Individual follow-up questions did successfully identify the separate Google TV and TV devices, so the failure was routing, not lack of inventory data.

## Changes
- Restrict the immediate Internet block/allow/unblock parser to simple, single-operation requests.
- Reject conditional or compound instructions mentioning `if`, `when`, `whenever`, `unless`, `once`, `while`, `before`, `after`, `as soon as`, `provided that`, `depending on`, `based on`, semicolon-delimited actions, or multiple sentences.
- Such prompts now fall through to the semantic/automation path; a compound instruction is **never sent directly** to a one-device Internet-room resolver by the immediate parser.
- Preserve the existing authoritative Internet-room Switch semantics: `off` blocks access, `on` allows access.
- Add regression tests for the exact live prompt, several conditional variants, and unaffected simple immediate commands.

## Evidence and limitations
This change fixes *only the routing misclassification*. It does **not** deploy a 60-minute cumulative usage allowance. The five-rule AI proposal was not executed and must not be used unchanged: TV (4221) is a power-metering smart plug, so socket `switch=on` does not establish actual TV use; the Internet control must be verified by exact ID and real switch commands, not assumed to support synthetic `blockInternet`; the reset must use an observed unblock transition; and proposed Hubitat Rule Machine schemas must be verified against the live tool contract.

A future stateful rule/application must handle cumulative usage intervals, reboot/persistence, duplicate/out-of-order events, standby power classification and unblock/reset ordering with explicit confirmation. No Hubitat writes are made by this code change. Live verification is required after installing the release.

Merge only after all three CI workflows pass.
