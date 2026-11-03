# v0.18.383 — source-attested status values for Q1 first-answer review

## Observed real baseline

The user ran the **exact frozen** Q1 legacy question `What is the hub health status?` on installed **v0.18.382**. The SHA-256 `b586998f15c01644355754722ae36cce273a5026d2c436046e6a441b05ebf23c` matches the registered question after `collapse-whitespace-v1` normalization. The displayed answer was clear and concise, reporting Hub Information Driver firmware/resources/radio conditions; its single `authoritative_hub_info_snapshot` receipt was source-successful but retained **only a list of field names**, not their actual reported scalar values. Independent source-grading of firmware, alerts, CPU/memory/temperature and radios was therefore **not possible from the diagnostic JSON alone**.

**Measured run:** 17.425s wall, 17.383s agent, 4.987s provider across **two Gemma 4 31B free rounds**, one local Hub Info snapshot (9.991s), discovery 2.385s, and one logical tool call. The metrics also reported 12.369s aggregated MCP HTTP; **do not sum overlapping metric categories** or claim a controlled before/after latency effect. Target for common status requests is under 15s, so this observed run exceeded target. The receipt classified read effect/nonmutating; underlying device refresh/update-check commands were part of the existing snapshot implementation. No new control calls were authorised. `model_delivery_verified=false`, `first_attempt_verified=false`, `deployed_build_sha_verified=false` remain correct and prohibit claiming a certified first-attempt baseline from this one run.

## General improvement

The common Hub Information Driver tool already returns a typed JSON snapshot to the model. Its public evidence receipt used to discard all measured values. This release adds a **strictly allowlisted, source-scoped value projection** at the existing ToolExecutor evidence boundary for **firmware, resources and full** scopes:

- Accept only source-successful snapshots whose requested scope exactly matches the returned scope; include driver-reported CPU, free memory, temperature, database size, firmware/version, uptime and bounded radio statuses when validated by type and format.
- Keep source-provided units where allowed; **no defaulting unknown to zero, healthy, disabled, up-to-date or no alerts**. The derived `update_available` flag alone does not become raw source proof. Free-text alert payloads are omitted rather than exported.
- Never include hub source label, device IDs, IPs, arbitrary status strings, credentials or raw driver payload in the public evidence receipt. The actual model tool data and the natural answering route are unchanged.
- Include existing-tool-only diagnostics for the number of internal device polls, the configured 500ms poll sleeps, number of refresh/update-check commands and whether the firmware snapshot settled. These are operational counts, not new network reads, source timestamps or proof of physical hub health.

**Quality hypothesis:** A reviewer can source-check individual reported values from the *same* HomeBrain response instead of requesting another hub read; poll counts identify why an authoritative snapshot was slow. Source values **do not prove** model wording correctness, independent external firmware freshness, first attempt or naturalness.

## Offline tests, rollback and next checkpoint

Synthetic tests cover all three scopes, exact numeric values/units/firmware, unsupported/malicious strings, sensitive household attributes, false “no alerts”, source errors and scope mismatches, stable tool counts and 1-versus-2 poll scenarios. The frozen Q1 fixture/rubric and model route remain unchanged.

Before: real v0.18.382 receipt had 0 source-value fields; wall 17.425s. After: code changes with offline tests; **installed v0.18.383 source-value coverage and latency NOT MEASURED**. No claims of accuracy improvement, Claude parity or faster execution from CI alone.

Roll back the projector and poll diagnostic fields if live payloads violate privacy or status interpretations change. The next user-assisted acceptance can be another **unchanged registered read-only common status question** on installed v0.18.383, with full answer and Technical JSON, only when needed; do not conflate a repeated health acceptance run with an independent first attempt. Production Internet-blocker work remains paused by user request, writer disabled, no live Hubitat/HA config changes.
