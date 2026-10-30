# v0.18.257 — Preserve independently observed sensor evidence across final synthesis

## Live regression
The original HomeBrainOS v0.18.256 model fetched:
- 20 independently source-timestamped Bathroom-light switch observations from Historical Journal, plus 20 reception-only copies.
- Independently source-timestamped motion history for additional device IDs (four rows from 7746 and two from 7908) and queried other input device histories.
- An app configuration and device dependents.
Nevertheless, the published archive-based digest said sensor timing was still required and omitted every sensor observation. The finalizer was replacing model text with a light-only Journal digest, thereby discarding valid input evidence already retrieved.

## Architectural correction
- The **single original unified evidence collector** now projects independently read motion/occupancy/presence histories into a bounded, deduplicated, source-reported input stream with original timestamp and device ID.
- The same stream is supplied to the **existing model evidence packet** and the in-loop Historical Journal discovery checkpoint. The model can compare actual independent observations and select further permitted reads without rereading their histories.
- The **existing source-verified Historical Journal digest** now includes a concise independently observed sensor timeline. These are **input reports, not evidence that any sensor initiated a particular light**. Source-time order is preserved; a sensor that reported motion after a light activated does not retroactively prove it initiated that activation.
- Empty or unusable non-target history read results are represented as visibility gaps, not inactive device evidence.
- The remaining-cause statement now accurately reflects that some source-timestamped sensor history *has* been obtained; a controller dependency/execution trace is still needed for causal attribution.
- Regression tests cover generic journal + motion events, final model/journal reconciliation, empty reads and exclusion of mutating tool receipts.

## Safety, latency and outstanding work
No new tool permission, write path, automation edits or live Hubitat change. The model still decides which relevant devices and controller sources to read, and the final proof contract remains bounded to verified source receipts.

The live 0.18.256 run also reported 11 `gateway_operation_rejected` counters and 12 model rounds. That merits a separately instrumented gateway-contract study before speculating about which tool schemas were rejected; this release does **not** claim to fix operation rejection or make the source decision verified.

Merge after all repository CI checks are green. Live add-on update remains separate.
