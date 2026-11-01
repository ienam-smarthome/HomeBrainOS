# v0.18.334 — Q1 privacy-safe publication handoff observation

## Problem and scope

The general device-telemetry completion boundary can replace the incoming AI outcome with a long, deterministically rendered source report. The newest v0.18.333 trace is visibly safer and avoids the duplicate clock warning, but still used 11 model rounds to deliver a report rather than a natural explanation. We cannot safely declare that the incoming message was an unmodified model draft, or that it would have been more correct than the source-derived report.

This release adds `investigation_coverage.publicationBoundaryShadow` **only for a verified typed device-history projection**. It exposes a fixed schema, incoming-message-present flag, coarse length buckets, whether finalisation replaced the incoming text, and explicit `incomingVerifiedRawModelDraft=false`, `factualQualityMeasured=false`, `publicationGuardPassed=null`. **No raw model text, household content, timestamps, device names, or source excerpts are retained in these shadow fields.**

The existing deterministic publication boundary, generic validity checks, read-only model-tool limits and unresolved causal verdict remain **unchanged**. The shadow does **not** judge model answer quality and cannot enable unconstrained publication. No extra model/tool calls.

## Controlled comparative experiment

`python scripts/answer_quality_comparison_prompt.py --case-id aq_network_broker_vs_device_health` produces the already-curated, hash-pinned, **model-neutral and no-tools** offline evidence packet for either Claude or Gemma. It contains only the source packet, not private reviewer rubrics. Existing `scripts/answer_quality_fixed_packets.py` verifies input identity and first-attempt run metadata. Do not treat one Claude response to this question, or two changing live Hubitat windows, as a scored same-packet Gemma-versus-Claude comparison.

## Baseline and acceptance

The prior observed live runs (changing source windows, same question) were v0.18.331 **43.533s/10 rounds/13 tools**, v0.18.332 **55.132s/11 rounds/13 tools**, and v0.18.333 **41.885s/11 rounds/7 tools**. These are diagnostics, not a controlled A/B speed or answer-quality gain. This release is **not** evidence of faster/more natural answers; the benchmark remains **NOT MEASURED** until actual paired outputs are human-reviewed.

Tests reject private-text leakage and unknown publication-strategy labels, verify source-typed runtime integration and no write changes, and ensure the same 18 fixed offline packets can be rendered without leaking rubrics. Full release CI required prior to merge.

## Rollback

Revert this shadow module, its one completion call, and the version bump if any metadata or integration failure arises; ordinary answer publication was never changed.
