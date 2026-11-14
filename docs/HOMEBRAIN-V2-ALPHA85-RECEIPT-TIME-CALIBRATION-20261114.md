# HomeBrainOS V2 alpha.85 — temporal source coverage and physical-outcome calibration

**14 November 2026.** V2-only, general model-led evidence-quality refinement. No V1 runtime changes, live hub actions, fixed device mappings, scheduled work or deterministic answer rewriting.

## Why this change

A privately reviewed installed V2 alpha.84 natural causal first answer correctly located a recorded command issuer and the device's subsequent state report, and reviewed the current controller configuration. Its final model-led audit nevertheless made two avoidable proof jumps:

1. It confused the **oldest RETURNED history row** with the **start of the requested 24-hour lookback**. The question's focal time was inside the requested window, but the related input history returned rows beginning later. That means *missing returned evidence in the focal interval*, not proof that the event fell outside the query or was purged by retention.
2. It treated a later device-reported **zero-power sample** as independent physical confirmation, while the receipt also showed intervening nonzero power readings. Timestamped telemetry proves what was reported, not the independent physical mechanism or uninterrupted activity.

The identifying private evidence, tool receipts, device names, IDs and household timestamps remain outside GitHub. Earlier independent source reviews covering lighting, heating, humidity and stale-device investigations recorded related cross-domain difficulties with event chronology, missing historical member coverage and unsupported causal/physical certainty. This is a transferable evidence-contract issue, **not** a device-specific pattern or an independently established population failure rate.

## One general implementation change

Modify the existing **source-sufficiency** and **final contradiction audit** guidance in `hubitat-mcp-ai-v2/rootfs/app/investigation_review.py`. These remain two optional model-led stages rather than a new planner or validation pass:

- Explicitly compare requested since/until or relative-lookback bounds with the focal timestamp **separately** from the earliest/latest returned row; do not infer that the source's retention boundary equals its oldest returned sample.
- When no matching event-time input was returned, the model may independently select a proportionate advertised READ-ONLY source or report the gap. The client does not choose a tool, force the monitor, invent a reading or decide causation.
- Before claiming an outcome, account for intervening timestamped state/measurement reports. Label `0 W` or switch-off as **device-reported**; no independent physical confirmation exists merely from correlated device telemetry.
- Preserve supported positive command issuers and exact timestamps. Keep contemporaneous configuration distinct from the historical internal decision path.

The original request/response receipts, evidence indexes, role distinctions, permission checks, write approval lifecycle, and fallback behavior are unchanged. A completed audit remains *a completed model pass*, **not** a correctness certification.

## Synthetic verification and limits

The existing V2 tests now check that both checkpoints carry this general instruction, that original requested `sinceTimestamp` and the later oldest-returned time survive the already-existing bounded receipt index, that unexpected secret fields stay excluded from the index, and that the final review remains tool-free. Tests use fictional sources and do **not** claim the installed cloud model will choose a better query or fix a particular wording. Existing approval and native-action tests must remain green.

**Cost:** No additional mandatory model round, native MCP request, historical poll, cloud provider or fallback call. When the optional reviews run, their slightly longer instructions can consume slightly more prompt tokens (and therefore a small amount of provider credit); this has not yet been quantified. Review rounds continue to obey existing deadlines.

## Next acceptance (installed, private)

After updating V2 Preview to alpha.85, choose genuinely **new**, uncoached read-only questions from different domains, not the already-exposed incident. Collect original first answers and PRIVATE Technical JSON; verify the exact requested time-window start versus returned history timestamps, intervening observations, source gaps, reporter-versus-initiator, independent physical proof, tool failures, latency and model call counts. Manually score 0/1/2 for factual grounding, source completeness, causal calibration and usefulness. Compare across the existing Gate B programme (>=12 fresh cases / >=6 domains); do not infer success from passing CI or from a revised draft. **V1 remains unchanged.**
