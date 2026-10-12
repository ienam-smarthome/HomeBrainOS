# HomeBrain 0.17.10 — Direct-command versus upstream-cause verification

The 0.17.9 live investigation of Bathroom Light 1 at **07:53:36** correctly identified App 4013 as the direct setLevel(50) command producer and the configured LWR01 occupancy sensor as the most likely initiator. The output's alternative-cause section and certainty table correctly said upstream manual input was **not** independently excluded, but an earlier explanatory sentence still asserted that app provenance "ruled out a manual physical switch press."

## General reasoning integrity improvement

- Preserve the established distinction between *who issued a device command* and *what activated that app*. An app-owned command is one-hop provenance and does not establish a complete absence of manual/controller input upstream.
- Check positive exclusion claims based on the subject of the assertion, including active and passive sentence construction, rather than a single fixed phrase like "Manual Control: Ruled out". This applies to human/manual inputs, mode-change causes and upstream automations without hard-coding Bathroom or App 4013.
- Leave already-calibrated negative statements ("not ruling out", "without ruling out") unchanged and do not rewrite unrelated hypotheses such as a power failure.
- Reuse this check in both shared synthesis validation and final API serialization, so model rewrites cannot restore unsupported causal certainty.
- Add generic regression tests for the exact live contradiction, variant phrasings, passive voice, existing table calibration, valid caveats, and absent direct-app-command evidence.

## Performance and scope

The live 0.17.9 investigation used 12 MCP/local tool calls, 5 model rounds, and one evidence retry, taking **43.7 s**, including **37.8 s** with the model provider. This release addresses the demonstrated **causal correctness** defect. It does not claim to solve model latency; further investigation should separate necessary evidence-gathering rounds from redundant repair passes before reducing tool budgets.

Read-only investigation and existing device-write confirmation gates are unchanged. Live Hubitat verification is still required after updating.
