# HomeBrainOS 0.18.85 — Focused app evidence in whole-hub audits

## Live regression: 0.18.84, 23 October 2026, 23:00 UTC
- A full read-only audit and optional AI analysis completed, with the actual participating model correctly identified as `gemma4:31b` using Ollama Cloud on Free tier. Model attribution in 0.18.84 is verified.
- The audit reported 204 devices, 160 automations, 265 scheduler entries and a **saturated newest-200-row log sample**. The named target apps Life360 (4061), Device Status Report (3977) and Octopus Energy (3933) were not independently investigated; the AI instead summarised unrelated top-three system health findings.
- Optional AI described an offline Bedroom 3 Mesh status and watchdog events as proof that manual control and automation triggering were unavailable. It also called the Lighting Automation Heartbeat monitoring non-functional based solely on an old last-event timestamp without any established reporting cadence, and treated `pctBusy` as a portion of the hub's available processing cycles. Those are unsupported extrapolations.

## Changes
- For questions naming numeric `app ID` instances, conduct at most **three** additional read-only, 6-hour, capped-at-80-row `hub_get_logs(appId=...)` checks before analysis. Include exact matched app IDs, matching ERROR/WARN and LimitExceededException counts, explicit log coverage limitations and performance ranking presence/unknown state. No time-filter or log-history completeness inferred.
- Display a **Requested app checks** section in the deterministic report and include it in the bounded AI evidence packet; instruct the analyst to directly address these requested apps rather than silently substitute unrelated general findings.
- Correct the specific unsupported claims of manual-control failure, non-functional heartbeat and high CPU usage, conditional on the host report's actual source coverage. Keep directly observed offline states, old timestamps and pctBusy rows intact.
- Add regression tests replaying the three named app IDs and the 0.18.84 overclaims. Preserve free-first routing, model receipt and no-write policy.

## Limits
Read-only log samples do not establish 24-hour completeness, app performance outside top-ranked rows or actual manual command outcomes. Additional app reads are capped, no Hubitat mutation or model-tier change is made. This patch improves question coverage and correction of demonstrably unsupported claims, but does not certify Claude-equivalent reasoning.
