# HomeBrainOS v0.18.205 — Consistent V2 evidence frontier and publication diagnostics

## Live replay (29 October 2026)

v0.18.204 correctly retained focus on Google Nest Hub (7934), identified historical command issuers Adhan Player (1679) and 00 Google Calendar Notifier (4080), correlated the single sampled excessive-load WARN at 06:01:28.979 with volume=50 at the exact same source-reported timestamp and skipped redundant final model synthesis. Duration improved from 54.079s to 22.112s. Its evidence remained incomplete: the warning cause was still not established.

Remaining contract inconsistencies:
- The causal coverage hint suggested a broad past/WARN query with only a higher limit after a target-scoped WARN sample already returned the warning. Host duplicate scope protection rejected this proposal.
- The host-published generic incident was internally reported as `claim_publication.status=unstructured_withheld`, `fallback=true`, `rejected_reasons=[non_structured_answer]`, despite the model-only synthesis being deliberately skipped and its claim protocol not being invoked.
- Text for a single sampled warning incorrectly referred to gaps "between those rows."

## Implementation

- A target-scoped WARN follow-up is suggested only if a verified target-specific warning **has not already been returned**. Once independently observed, repeat-broad-log advice is omitted, and the model may investigate a distinct grounded historical time window, attested apps/source or runtime measurements if available. No auto-execution, source-coverage overclaim or change to the write guard.
- At the causal coverage challenge boundary, explicitly tell the model that repeated same-scope WARN queries are not discriminating and that stating the evidence limitation is a valid answer when no new reliable source exists.
- When the host itself publishes a source-authoritative unattributed incident, mark claim-publication authority `host_incident_receipts`, status `host_authoritative_incident`, with zero fabricated model-claim rejections or model fallback. The separately available structured claim catalog remains the same. Model-selected claims for other question classes remain subject to their existing strict validator.
- Single-row warnings explicitly state that the sampled warning cannot establish duration or absence outside its returned instant. Multirow groups retain the guard against continuity inference.
- Add general regression tests for both the genuinely missing target-WARN case and the already-returned WARN case, a zero-row target WARN, and accurate single-row incident wording. Extend the v0.18.204 end-to-end replay to assert truthful host publication status.

No production Main Ask, Hubitat configuration, rules or devices are modified. V2 remains experimental and READ-only. These changes improve honesty of diagnostics and the evidence-guided tool budget, not proof of any warning's runtime root cause.
