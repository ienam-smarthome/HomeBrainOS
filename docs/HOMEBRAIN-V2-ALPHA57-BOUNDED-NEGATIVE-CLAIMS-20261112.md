# HomeBrainOS V2 alpha.57 — bounded negative-claim provenance

**Date:** 12 November 2026  
**Starting version:** 2.0.0-alpha.56  
**Candidate:** 2.0.0-alpha.57 (V2 only)  
**Purpose:** improve model-owned evidence calibration, especially negative and universal claims, without incident-specific patches.

## Why this refinement

A private installed alpha.56 first-answer capture was reviewed against its own original successful MCP receipts. It was substantially better than the previous alpha.55 causal case: it preserved the bridge's state-reporting role and correctly left initiation unverified. The first answer was scored **6/8** across factual grounding (1), source completeness (1), causal calibration (2), usefulness (2). However, its summary still made a broader absence claim than a narrow, no-command-row event search and a text-pattern log search justified.

This single nonblinded regression run does not establish across-domain accuracy or a general improvement in the cloud model. The remaining failure class is **source-bounded negatives**: a statement about what one query returned is sometimes promoted into a statement about what an entire hub, recorder, application or physical device did not record or do.

**Never publish private Technical JSON or actual household device names, IDs, event timestamps, local addresses, credentials or raw logs.** This note records the general problem and synthetic implementation only.

## Design

- Keep V2's model-selected MCP reads, original receipts, existing source-sufficiency checkpoint, and alpha.56 tool-free final audit; no new model round and no forced additional MCP call.
- Strengthen the final model's **counterexample test**: if a missing event, command, value or alternate initiator could exist outside the checked filter/window/rows while all successful receipts remain unchanged, a universal negative does not follow.
- Require the model to phrase negative findings with their actual **source and query scope** (including text-search patterns, event/attribute filters, lookback boundaries, source caps and freshness). Apply the same check to the final conclusion, not just earlier caveats.
- Supply the final existing audit pass with a compact **receipt scope navigation index**. It is assembled from previously returned *redacted* request arguments and selected source-provided scalar counts/limitations, not inferred causes or new observations. Its bounded structure omits individual device samples, raw logs, arbitrary source text, hidden input fields, credentials and untrusted instructions; the original receipts remain authoritative.
- Do not add a host-side causal verdict, answer rewrite, claim blocker, deterministic source selection, device-specific rule, source-specific command absence inference, or write permission. Tool-free audit still forbids unexpected tool execution and falls back to the previous draft if its model call fails.

A scope index can itself omit relevant evidence (bounded to the first sixteen tool receipts). It explicitly reports omitted receipt count. Source-derived summaries can help model navigation but cannot certify completeness, physical observation, or accuracy of a conclusion.

## Synthetic verification

The new fictional tests exercise:
1. Separate state-filtered and unfiltered event queries, preserving their distinct limits and absolute time windows.
2. A zero-match text-filtered log search, preserving the actual pattern and returned matched count without interpreting it as the hub recording no action.
3. A positive command-containing receipt, showing that observed command issuers must not be discarded simply because the wider causal explanation remains unknown.
4. Failed tools and catalogs not being treated as successful evidence.
5. Bounded receipt indexing and omission of secret fields, log entries and individual samples from the compact index.
6. Delivery of the index to the final tool-free model round without adding reads or changing original MCP results.

These tests establish only data flow, boundedness, and safety. **They cannot prove that Gemma will always correct an overbroad negative claim.** Avoid grading scripted replies as live model reliability.

## Gate B acceptance after install

After GitHub CI passes, confirm add-on manifest, API and UI all report `2.0.0-alpha.57`. Use fresh, genuinely different read-only first-answer cases as well as a controlled repeat of the prior causal question. Score against ORIGINAL successful tool receipts, including exact chronology, lookback, filters, caps, reporters, positive command issuers, competing controller paths, and missing discriminating evidence. Retain factual grounding, source completeness, causal calibration and usefulness 0/1/2; n/a only when truly inapplicable. Do not grant a production cutover from a coached replay or a single case.

Observe `source_review_invoked`, `final_claim_audit_invoked`, `final_claim_audit_status`, model rounds and latency. Positive causes should be stated when actually verified; calibrated uncertainty must not conceal a real recorded issuer or direct sensor reading.

**Boundaries:** V1, the independent monitor archive, Hubitat native MCP read/write surface, confirmation gates and stored source evidence are unchanged. No live user environment was altered by this GitHub candidate.
