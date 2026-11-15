# HomeBrainOS V2 alpha.103 — scoped source-verification contract

**Date:** 15 November 2026. **Scope:** isolated V2 Preview only; PRIVATE live MCP receipts not committed.

## Evidence and failure
Two installed alpha.102 exhaustive-history questions each selected a successful native `hub_list_device_events` call filtered to `switch` (one with eight returned switch reports, one with zero). Neither source could enumerate every recorded command, but each *could* support a bounded statement about the switch rows it returned. The alpha.102 typed completion verifier returned a generic unverified refusal for the entire answer. Both source review and final audit had completed, and no native writes were recorded. Hub & Device Monitor was offered but not read. This is a narrow output contract defect, not proof of physical state continuity or missing command activity.

## V2-only change
- Preserve all **verified returned state rows**, offsets, exact adjacent report gaps and original source sinceTimestamp even when the model chose a filtered native event read.
- Verify command inventory independently: when filtered, any command rows shown are only rows visible in the filtered result. State **command coverage not verified** with a proportionate recommendation for a model-selected unfiltered read; never claim absence of commands.
- Explicit `structured_history_verification.command_verification_status` and `command_enumeration_scope`; `source_event_rows` is the count of original parsed rows for a successful projection, null when unverifiable rather than a fabricated zero.
- Include nominal end of relative lookback as a *derived* clock value, not an independently observed end; return-source retention and uninterrupted state remain unverified.
- Preserve fail-closed for missing, failed, ambiguous, mismatched, capped, oversized, malformed or wrong-attribute receipts. The model still independently selects tools and authors ordinary causal, current-state and write answers.
- No new compulsory tool call, LLM round, poll, private source replay, native write, cloud provider/routing change, or V1 edit.

## Validation and acceptance
Synthetic fixtures cover eight returned state reports with filtered-out command history, a zero-row filtered source, unfiltered mixed state and command rows, unsafe/malformed sources, cross-domain state histories, privacy and causal non-interception. The existing scripted agent lifecycle continues to assert zero extra reads/model rounds in the unfiltered path.

Gate the PR on exact-head full Python/V2 test suite, container smoke, metadata/repository validation, UI fixture and scorecard checks. After installing alpha.103, run one fresh independent read-only exhaustive history question *without coaching source selection*, inspect PRIVATE original receipts row-by-row, separately assess command-source limitations and cost/latency, and run an ordinary non-exhaustive causal question to confirm model-led reasoning remains intact. No installed source-real correctness is claimed by CI.

**Rollback:** revert alpha.103 if it exposes disallowed private source text, hides malformed-source failures, changes write approvals, or claims a command inventory from filtered evidence.
