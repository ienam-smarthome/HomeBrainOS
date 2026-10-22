# HomeBrainOS v0.18.58 — Related Rule Machine lighting-pair selection

## Live motivation
The 2026-10-22 v0.18.57 read-only audit retrieved exact Rule Machine apps 3600, 3602, 3931 and 3992, but only inspected the indexed settings of 3600 and 3602, the two lowest-numbered lighting candidates. Prior read-only investigation indicated 3600 and 3992 may both reference Bedroom 3 Light. The numeric heuristic prevented that more informative pair from being compared.

## Change
- Keep the same six ordinary app config reads and two secondary RM settings reads under the existing six-second / two-concurrent limits.
- Among current installed verified RM lighting candidates, preferentially choose the pair with at least two matching non-boilerplate name tokens (e.g. Bedroom, 3, Light). This is *only a scheduling hint* for which sources to inspect, not proof of the target device, trigger, action or overlap.
- If the label similarities cannot identify a convincing pair, preserve the existing stable numeric priority and stop after two.
- Retain strict native Rule Machine 5.x source-type checks before reading internal indexed settings; no generic raw settings exposed.
- Corroborate extracted IDs using the MCP device-dependents index. Only typed device ID overlaps from actual action structures can prove shared action targets; matching RM indexed reference keys alone cannot establish action direction, execution or conflict.

## Validation and benchmark
- Regression test models the four live lighting candidates, verifying the 3600/3992 pair is chosen over 3600/3602 and that equal names, generic labels and source types cannot fabricate action evidence.
- All three CI workflows required before merge.
- After deploying, rerun the read-only comprehensive audit. The independent Rule Machine **writing** benchmark should be performed separately against HomeBrain and Claude, with no creation commands until explicit user confirmation.
