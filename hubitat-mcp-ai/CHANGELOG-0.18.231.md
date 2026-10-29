# Hubitat MCP AI v0.18.231 — One coherent AI reasoning workflow

## Problem

Although Native V2 had a natural-language assessment stage in v0.18.230, the
**model's 10,000-character planning prompt still ordered it to output only
JSON claim IDs**. This conflicted with the final incident-reasoning contract,
encouraged device/app command-count reports and impeded using evidence to
compare competing explanations. Event references at final synthesis contained
only names/timestamps, not even the actual ON/OFF values or event actors.

## Architectural correction

- Replace the contradictory planning prompt with one concise, domain-general
  reasoning contract. It directs the AI to understand the user objective,
  compare possible explanations, choose discriminating READ tools, evaluate
  source relevance, and stop when no additional available read is useful.
  **No final answer schema lives in the tool-planning prompt.** The host
  keeps all read-only, ID, effect, schema and security controls.
- For the existing dated incident proof packet, include the independently
  source-projected **event value, source name and whether it was a target
  device state or issuing app command**. A name/timestamp alone is not an
  adequate causal reasoning input.
- Expand the source-based material-state vocabulary to thermostat,
  heating and ventilation measurements for cross-domain investigation.
  This is event typing, not a question keyword or device-name route.
- In the model planning transcript of a named device incident, prioritise
  actual observations over the verbose `source_claim_catalog` so the
  model is not nudged toward command-count summaries.
- When the model has already supplied a well-formed hypothesis with exact
  incident event anchors, reuse it in the final validated answer without
  a redundant model-only synthesis call. If it returns ordinary prose
  instead, use the separate short, source-linked reasoning synthesis.
- The final reasoning prompt asks for a likely-but-tentative explanation,
  a competing possibility and the one best observation to distinguish them.
  The independently checked renderer publishes short natural text and
  keeps detailed receipts in technical diagnostics.
- Still reject invented read IDs, timestamps, numeric details, unbounded
  certainty and unverified physical causation. Real user-confirmed causes
  remain separate from inferred device telemetry.

## Cross-domain tests

`pytest -q tests/test_investigation_v2_unified_reasoning_0_18_231.py`

Replays the lighting incident, tests device-state ON values and verified
app issuer labels, verifies heating temperature/setpoint evidence, checks
natural vs structured in-loop model responses, confirms no extra model
call for a verified draft, and rejects unjustified definite alternative
claims. Run complete repository test suites and add-on smoke checks before
merge.

## Remaining scope

This change removes a significant cross-cutting source of prompt conflict.
It does not make any particular model Claude-equivalent, prove that two
correlated events establish a root cause, recover historical hub data that
no longer exists or demonstrate general reasoning accuracy without live
cross-domain benchmark evaluation. No actual Hubitat device/rule write.
