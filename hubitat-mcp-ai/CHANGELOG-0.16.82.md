# 0.16.82 — Evidence-gated adaptive diagnostics

## Summary

0.16.82 keeps the accepted 0.16.81 adaptive performance retrieval architecture unchanged and adds a structural evidence gate for the diagnostic conclusions produced from those scoped reads.

The live 0.16.81 proof showed that retrieval was working correctly — three baseline reads plus one device-scoped and one app-scoped diagnostic read, zero agent model rounds, and one synthesis round — but the final model still filled evidence gaps with plausible mechanisms. In particular, sparse Google Nest Hub volume observations became a polling/state-update hypothesis, an unscoped LG webOS performance row became a network-latency hypothesis, and repeated SenseCap config-push rows were promoted into an unsupported 5–10 minute cadence.

## Evidence classification

Each successful `host_planned_performance_diagnostic` log receipt is now classified deterministically as one of:

- `diagnostic_signal` — explicit timeout/connectivity/failure or very-long-call evidence exists; a calibrated hypothesis consistent with that signal is allowed, while exact implementation defects and downstream user impact remain unproven.
- `repeated_activity` — repeated neutral activity is present; the pattern may be reported and compared with measured performance statistics, but it is not a causal mechanism.
- `sparse_or_neutral` — only sparse/neutral scoped observations were found; the targeted investigation did not reveal a mechanism and the answer must say so.
- `no_observations` — the targeted scoped read returned no retained observations; the mechanism remains unresolved.

An outlier that was not one of the adaptive scoped targets may not receive a mechanism hypothesis merely from its performance statistics.

## Structural diagnostic guard

The final validator now uses the adaptive evidence classification to enforce diagnostic boundaries rather than matching one-off wording variants.

- A sparse Google Nest Hub read cannot become a polling/state-update/network/blocking hypothesis.
- An LG webOS outlier that was not target-scoped in the current turn must be described as unresolved and as needing a targeted diagnostic read.
- Repeated SenseCap config-push activity remains useful evidence, but raw timestamps cannot become a recurring cadence unless host-derived timing explicitly classifies a regular cadence.
- `Highest Resource Usage` is neutralized to returned performance-percentage wording.
- `high average execution time` is reported as the measured average execution time unless a source provides a qualitative threshold.
- Same-second clustered reporting is not promoted into literal simultaneity.

The structural gate reports through the existing evidence-first performance repair category, preserving the established privacy-safe observability path without introducing target names or IDs as metric dimensions.

## Architecture unchanged

- Quiet broad-performance case: 3 reads, 0 agent model rounds, 1 synthesis round.
- Strong-outlier adaptive case: up to 5 reads, 0 agent model rounds, 1 synthesis round.
- No new provider planning round.
- No additional broad fan-out.
- Existing 0.16.79/0.16.80 host timing classifications remain authoritative.

## Regression coverage

New 0.16.82 tests reproduce the 0.16.81 live failure shape and assert that:

- the Nest Hub receipt is classified `sparse_or_neutral`;
- the SenseCap receipt is classified `repeated_activity`;
- unsupported LG network-latency and Nest polling hypotheses are removed;
- SenseCap's model-authored 5–10 minute cadence is replaced with the scoped row count plus the fact that no regular host-derived cadence was established;
- same-second Octopus activity is not called simultaneous;
- explicit timeout/HTTP 408/no-route-to-host evidence still permits a calibrated diagnostic hypothesis while preserving stronger causal boundaries.
