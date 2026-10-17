# v0.18.26 — Bound live investigations and retain verified read receipts at timeout

## Root cause
The API's existing `investigation_deadline_seconds` (default 90 seconds) was only passed to the request coordinator for broad performance, whole-hub audit, or broad automation diagnostic questions. Model-led source investigations, historical app-command verification, and ordinary causal/historical investigations could run for many tool/model rounds with **no request-level deadline**. A live Bedroom 3 Mesh investigation previously ran roughly 410 seconds.

The request coordinator already knew how to cancel tasks. However, `remember_verified_outcome` was called after the model loop had returned. A timeout during that loop could discard successful MCP read receipts even if the investigation had already retrieved useful facts.

## Correction
- Apply the same configurable investigation deadline to **all recognized read-only investigative intents**: source-code, model-led reasoning, named historical automation executions, causal/device history, and existing broad audits. Do not attach it to routine current-state questions, conversational turns, or state-changing requests.
- Mirror each **successful, nonmutating, sanitized MCP read receipt** into an isolated per-request progress checkpoint while the agent is running (at most 64 receipts). No model-generated text, failed reads, or write/confirmation receipts enter this checkpoint.
- If an investigation times out before model synthesis, cancel its backend task and return an **evidence-only partial** showing the completed reads and the precise timeout. Do not claim a diagnosis, missing historical execution, or physical acknowledgment from read success.
- Preserve previously remembered valid checkpoints; combine verified read receipts without duplication. Keep the existing HTTP 504 when no valid evidence has been collected.
- Return `success=false`, `status_verification=incomplete-timeout` and `outcome=unresolved` for partial timeout API results. Avoid re-running shared final synthesis over a timed-out partial message.

## Safety and scope
No additional MCP permissions, writes, confirmation changes, DeepSeek pricing/budget changes or model-selector changes. This is a response execution/cancellation boundary, not a guarantee that available history covers the requested date. A timed-out investigation requires further work to establish historical app-command causality. Cancellation is cooperative and provider network calls remain subject to their own transport behaviour.

## Regression tests
Read-only intent coverage, routine/control exclusions, cancellation after successful read evidence, rejection of failed/write receipts, checkpoint recovery, serialisation and existing timeout cases.

Live follow-up: install after all three GitHub CI workflows pass; repeat the exact 12 October 01:30 BST app 3950/device 7103 historical OFF-command verification from v0.18.25 and inspect model rounds, original event/execution reads, timeout status, and whether the result is correctly unresolved when matching evidence is absent.
