# HomeBrainOS 0.18.89 — Primary investigation objective architecture

## Why this change

Live 0.18.88 Groovy investigation for Device Status Report app **3977** correctly retrieved app source **code ID 1410** with **81,240/81,240 characters**, but the final response was replaced with a historical device-command attribution warning. The original user wanted a method-level excessive-load explanation for `setReportData`, line 64. A method causing app load and a past ON/OFF command are different kinds of causal claims. Six model rounds, eleven tools and a synthesis repair still failed to answer the actual question.

## Structural changes

- New immutable `investigation_objective.py` establishes **one authoritative primary domain** before tools: installed Groovy source, existing Rule Machine verification or general request. It carries the exact installed app ID and requested method where available, without enabling writes or assuming a source code ID.
- Agent routing, API finalization, final model synthesis and shared evidence completion use the same objective instead of separately recalculating conflicting policies. An explicit source investigation outranks generic Rule Machine and performance analyses.
- Source synthesis retains the **unfiltered current-turn tool transcript** and receives a source-specific method-oriented final instruction. The broad-performance post-processor, standalone performance synthesis contracts, incidental performance-log validation and event-causal answer shortcuts are not allowed to seize control of a source-code request.
- The historic-command guard for source analyses now requires an *actual, same-clause device-command dispatch assertion* (e.g. “App 3977 issued an OFF command”), not mere adjacent words like “sent report updates,” “executed setReportData” or “caused high load”. Explicit false command-dispatch claims remain subject to dated event evidence.
- Source retrieval, **candidate method-body excerpt evidence**, and claim/answer coverage are distinct. The source workbench exposes only a bounded list of method bodies that were lexically balanced and shown in full; ToolExecutor retains that typed list alongside source offset/page receipts without storing private Groovy text. A source method-level completion cannot be certified by method-name and exception keywords alone.
- Regression tests replay the live false-positive historical warning, real device-command assertions, app 3977/source code 1410, full-file but absent method-body evidence, proper non-Groovy rule routing and reduced broad-performance rewriting.

## Important limitations

- Lexically balanced Groovy excerpts are **candidate** method bodies, not compiler certification, complete call graphs or proof of runtime behavior. Method-level statements and `questionResolved` still require causal caution. The broader multi-specialist architecture has not been replaced; this is a shared control plane applied to the relevant boundaries, not a full rewrite of all specialist modules.
- Existing Hubitat `LimitExceededException` logs remain observed evidence; the precise root cause inside app 3977 remains unverified pending source method/caller and actual execution correlation.
- **No Hubitat writes, device commands, rule/configuration changes, model-tier changes or paid escalations.**
