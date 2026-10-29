# HomeBrainOS v0.18.200 — factual evidence receipts and model-led source follow-up

## Why

The v0.18.198 live Google Nest Hub investigation correctly withheld unsupported app causation, but it used 11 reads, including unrelated/broad log samples, without obtaining a driver execution path. v0.18.199 supplied safe static source indexing but depends on an actual complete, verified source response.

## Changes

- New **source-backed factual evidence ledger** for independently observed device WARNs (including named-method durations), device-scoped command issuers, and verified complete static Groovy structure. Each item includes a READ receipt and explicit limits. The ledger does **not** certify arbitrary model prose or causality; it does not turn a WARN, event or static call into verified runtime CPU attribution.
- New **evidence-derived source follow-up option** when a single verified device has diagnostic warnings but no complete code: first suggest a model-selected configuration READ for a driver identity; only suggest `hub_get_source(type=driver,id=...)` if the same target's configuration returned an independently attested driver ID. Report missing/ambiguous IDs and metadata-only source responses as blockers; never repeat a futile source query.
- Existing Native V2 host safety, typed IDs, single-call preflight checks, permission gates and model-led selection remain unchanged. No automatic MCP read, user keyword route, Hubitat write or production Main Ask change.

## Acceptance and next stages

CI tests exercise source method duration receipts without causal promotion, duplicate warnings, typed source evidence and preflight hints. Live verification must prove the model actually chooses a productive follow-up rather than broad logs, and must measure whether the selected driver source endpoint returns code or only metadata.

Atomic semantic claim-to-evidence validation for arbitrary free-form model conclusions remains incomplete. The factual ledger is a necessary host-side substrate, not a finished semantic gate. Future work should add a structured claim protocol with independently validated receipt references and actionable runtime tracing when available. No causal conclusion about Google Nest Hub is claimed.
