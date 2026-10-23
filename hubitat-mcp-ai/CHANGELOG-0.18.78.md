# HomeBrainOS 0.18.78 — Model-led, evidence-first comprehensive hub audit answers

## Live finding
A live v0.18.77 user test returned a 38.6-second, host-assembled `comprehensive-system-audit` result with `model=null`. Although the audit acquired 205 devices, 160 automations, 267 scheduled jobs, bounded log findings and top-ranked performance samples, the response never invoked Gemma to **reason across those facts**. The add-on's `comprehensive_audit_ai_analysis_enabled` setting was defaulted to `false`. When enabled previously, Gemma was shown only the first 7,000 characters of the lengthy report, which can exclude all performance leader rows and scheduler details.

## Changes
- Chat-originated comprehensive-system-audit requests now default to **one optional, no-tools AI reasoning pass**, using the user's selected model tier (Free remains the default). **Explicit `comprehensive_audit_ai_analysis_enabled=false` continues to disable it.** This setting may persist as `false` for existing Home Assistant add-on installations; users must enable it in the add-on configuration before testing.
- Pass the original user question to the AI for all eligible comprehensive chat requests. The model is asked for three evidence-backed priorities, comparisons, plausible competing explanations, confidence and the best next read-only verification, instead of merely a list of warnings.
- Create a **bounded, source-qualified audit reasoning packet** drawn from the current request's deterministic audit sections: health/coverage, staged timings, offline status, scheduler and owner uncertainty, top performance entries and relevant scoped logs. Skip sprawling quiet-device lists. Preserve log truncation and current-data limits.
- Move the clearly labelled AI reasoning **to the start** of the full report; retain the deterministic evidence detail below for auditing. Model opinions are not new Hubitat facts or permission to change devices.
- Bound the model pass (18 seconds, no MCP tools), continue returning the deterministic report if the model is unavailable, and leave automatic repair/confirmation workflows unchanged.

## Limitations
- This is not a claim that HomeBrain's inference matches Claude's quality. The AI summary is an interpretation of the read-only host evidence; it cannot prove causes that are not shown. A complete independent cross-model comparison still requires the same source packet and a human-reviewed scoring rubric.
- This does not reduce the approximately 26 seconds of fresh device inventory acquisition observed in the live report. That is a separate latency optimization.
- Existing installed add-ons with the setting saved as `false` will continue to use the host-only path. Enable **Comprehensive audit AI analysis** in Home Assistant add-on options for model-led audits and keep the Free tier selected to avoid automatic paid usage.
