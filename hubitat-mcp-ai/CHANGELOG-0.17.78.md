# HomeBrain v0.17.78 — Dated incident retrieval no longer depends on "deep" wording

## Reproduced live defect

The user's ordinary, detailed v0.17.77 causal question about Livingroom Light 1 at 19:55 on 14 October returned a safely qualified historical uncertainty result, but still performed 5 model rounds in ~29.5 seconds, with no `skills_early_focal_stop` counter. Exact source reads ran near finalization, not before model exploration.

The earlier early-read path in `mcp_agent_orchestrator.py` depended on `deep_causal_request`, derived by matching specific effort words (e.g. "deep", "investigation", "root cause"). The user's explicit question described historical ON/OFF, preceding commands and producer logs without those effort words. The code therefore skipped the early read for precisely the same evidence need.

## Correction

After the trusted subject prefetch, any causal question with a uniquely named switch and an explicit dated ON transition now asks the existing source-plan builder whether the requested ON boundary is missing. If so, the host executes exact-window switch history and producer app logs *before* optional causal fast exits and any model/tool rounds. This is independent of the user's terminology or requested thinking effort.

If exactly one historical ON is obtained, normal graph-based investigation continues. If the source gives zero rows, multiple ambiguous ONs or fails, the answer remains source-calibrated and may stop early without spending provider rounds attempting to reconstruct expired events. No case may treat a command as proof of subsequent physical ON.

## Regression

A production agent-level test uses the user's exact question (which intentionally does not match the effort classifier), injects the earlier command-history evidence, and verifies that both exact native history and producer execution logs are checked before any model call. It requires `skills_early_focal_stop=1`, zero model calls and verified no-cause language for the expired-history case. Existing causality and confirmation tests remain part of CI.

## Safety and scope

Read-only historical queries only. No device commands, rule changes, Hubitat configuration changes or changes to Internet blocking. The upstream native device history remains bounded by Hubitat's accessible event store; this release cannot reconstruct evicted events. An external journal remains the long-term solution for older event forensics.

## Live acceptance

Install 0.17.78 and repeat the exact prior question. If the old native ON remains unavailable, expect `skills_focal_state_window=1`, `skills_focal_producer_logs=1`, `skills_early_focal_stop=1`, and **zero model rounds** on this host-completable path. If the historical ON reappears, the ordinary evidence-graph investigation will continue.
