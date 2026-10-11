# 0.17.0 — Adaptive cross-integration causal investigations

Instead of limiting every unexplained bridge-reported light or switch transition to the two highest-ranked same-room occupancy sensors, HomeBrain can now expand the search using a bounded, general candidate graph.

## Investigation engine
- Preserve the existing hierarchy: **direct command producer > execution/log provenance > ordered controller and sensor correlations > unresolved**. Direct Hubitat command attribution is not changed.
- After room-first candidates cannot establish a repeatable preceding event, use cached, capability-grounded device metadata to propose additional motion/presence sensors across rooms and integration bridges. No hardcoded device ID, LWR01 name, or special Bathroom logic is introduced.
- Rank available candidate devices by configured external automation topology (where supplied), full room/label and parent references, physical-vs-derived context, and attribute-shape evidence. Metadata helps choose what to read; it never establishes what triggered a past action.
- Read at most **10 additional device histories** in batches of up to **3**, recompute hypotheses after each batch, and stop early when a repeated event-time preceding correlation is observed.
- Examine timezone-aware signed event deltas and repeated ON/OFF relationships. A sensor report *after* the device transition does not become evidence of a preceding trigger. A configured automation is a candidate pathway, not proof of execution.
- Present the best timestamp-supported upstream clue prominently while retaining **exact initiator unresolved** unless direct command/execution evidence exists. Report unexamined indexed candidates and missing cross-integration inventory explicitly; absence of a checked match is not proof of no cause.
- Continue to distinguish shared reporting bridges, downstream brightness/recovery apps, physical controller events, and true initiating commands.

## Verification
- Synthetic Bathroom/bridge occupancy benchmark modeled after observed timestamps: an outside-room occupancy signal leads the requested light transition and repeats at several earlier transitions; unrelated in-room sensors occur later. No hardcoded name is required in implementation.
- Counterexamples: after-the-light sensor updates, coincidental timestamps in different timezones, topology association without execution proof, devices advertising broad capabilities but exposing lux only, and incomplete evidence coverage.
- Host integration acceptance checks that adaptive exploration leaves the two-sensor room cap, stops on repeated upstream observations, and remains bounded.
- Privacy-safe new metrics: adaptive candidate batches, additional read count, sufficiently-supported stop, and unexamined candidate budget.

**Limitations:** This release can only search devices exposed in the cached Hubitat identity manifest and matching supported motion/presence attributes. It cannot automatically inspect Home Assistant's external automation traces without an authorized integration; timestamp correlation is not direct proof of a specific HA automation. The user should not infer full-home source coverage from a partial candidate search.

Read-only. No Hubitat automation or device is modified.