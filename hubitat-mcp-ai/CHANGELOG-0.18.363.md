# Hubitat MCP AI v0.18.363 — correct delayed Rule Machine refusal status

## What changed

- **Fix:** A verified scheduled command such as `block TV after 15mins` now reports `request_class=write`, not `live-read`, even though an immediate-control-only safety guard correctly excludes delayed commands from instant execution.
- **Fix:** When the installed Hubitat MCP server exposes native Rule Machine document creation while HomeBrain still has the legacy shortcut compiler, the blocked request is **Unresolved**, not green **Success**. An unavailable/unverifiable guide also yields Unresolved, with a distinct safe diagnostic counter. Neither case queues a confirmation or sends a write.
- **Clarity:** The response starts with the actual outcome and briefly explains the API mismatch and lack of a queued rule.
- **Regression tests:** Exact initial wording, provider-free short circuit, read-only guide only, complete no-write boundary, review-only intent safeguards, and outcome counters.

## Safety and limitations

**This does NOT implement native Rule Machine creation.** The server requires `operation=create,args={parent_id,name,changes}` with installed, capability-specific native fields and supported one-time time semantics. These are not yet verified. Renaming legacy `addTrigger/addAction` fields or creating an empty live shell remains prohibited. No live Hubitat or Home Assistant operations were performed by development. Existing legacy writer support and confirmation guards are retained.

**Measurement:** Actual first-answer quality, latency A/B, native scheduling success and follow-up live installation **NOT MEASURED**. Test pass is not a model-quality score. Rollback by reverting the release; the existing native-writing refusal must remain active.
