# HomeBrainOS 0.18.410 — source-verified native type vs unverified writer

## Observed v0.18.409 live evidence, 5 November 2026

The user supplied an installed v0.18.409 live read-only identity comparison for app instance 169. Four MCP calls, eight free Gemma Cloud rounds, **29.962 seconds total** (provider **25.999 seconds**). This is one observation, not a controlled latency benchmark.

The published typed receipts established:
- An exact Hubitat installed-app inventory row with id=169, appTypeId=18, reported type Rule Machine, user=false and parentId=null.
- An exact Hubitat type-catalog row with id=18, name Rule Machine, system=true, isBuiltIn=true. The same filtered catalog also included a *different* legacy type id=19; matching by name alone would be ambiguous.
- Target-matched app configuration with parentAppId=null and 42 child-app rows returned in one page. This shows reported parent/child structure, not that every child is a Rule Machine rule or that the page is the full rule inventory.

The prior v0.18.409 classification presented **native class/parent verification unresolved**, even though the trusted catalog's exact numeric class ID match and built-in classification had been positively observed. That conservative policy was written when type IDs were missing; retaining it now discards positive source evidence.

## Generalized evidence classification correction

- Independently establish **source-verified built-in app-type membership** when a target-matched installed-app type ID exactly matches a Hubitat-sourced type-catalog ID, all matched entries agree on a single class name equal to the instance's source-reported type name, all matched types explicitly say system=true and isBuiltIn=true, and all matching instance rows report user=false. Missing, conflicting, malformed, community or type-name mismatching data remains unverified.
- Independently establish the **source-observed parent role** only when the same exact instance is reported as parentId=null by installed-app inventory and a matching read-only app configuration reports parentAppId=null and at least one returned child-app row. This is not certification of every child's class or a complete rule count.
- When both identity and parent role are independently supported, mark the app-class investigation source-complete and explain the positive result in natural language and Technical JSON. A single built-in ID association without parent-role evidence verifies the *type* but does not fully resolve a *parent* question.
- Preserve the separate **Rule Machine native writer authorization: false**. These reads prove no one-time date-trigger schema, Rule Machine parent write preflight, source code body, UI form contract or safe write execution. Do not modify or unlock native Rule Machine authoring. No new MCP requests, model rounds or tool privileges.

## Safety and regression

Tests include exact source ID matches, duplicate same-name type records, catalog built-in flags, missing flags, type-name mismatch, conflicting catalog records, target-matched root/child evidence, absent parent role, and shared completion proof/status. The source-only publisher remains active even for positive identity findings, avoiding unsupported model assertions.

Post-update installed acceptance and response-time impact remain unmeasured. The v0.18.409 MCP evidence itself is read-only; it does not establish successful Rule Machine rule creation.
