# Hubitat MCP AI v0.18.230 — Model-grounded, naturally phrased causal hypotheses

## Why

v0.18.229 blocks an objectively wrong conclusion when evidence from the
user's requested incident date is missing. But even with relevant evidence,
Native V2 still coerced the model's entire final answer to numeric claim
IDs and substituted a robotic claim catalog. This release changes that
**presentation authority** within experimental Native V2.

## General mechanism

- For an independently verified **single target** with at least two
  incident-period material events, the existing end-of-read-loop model
  synthesis may produce one short tentative causal hypothesis rather than
  a JSON catalog of unrelated command counts. It uses the **same model**,
  does not gain new tools, and does not call any Hubitat write operation.
- The model must return a structured proposal containing the natural-language
  hypothesis, `confidence=possible`, at least **two distinct exact source
  event references** (`read`, event name and timestamp), and one useful
  distinguishing check.
- The host validates all event references against the same independently
  verified device-scoped, dated source window. Invented or mismatched IDs,
  events, timestamps and numeric details cause rejection. Explicit assertions
  of certainty are also rejected; successful proposals are rendered as
  "**Possible explanation:** ..." followed by at most one next check.
- If the model does not comply, the original fact-validated host fallback
  remains authoritative. The user gets no raw model proposal or fabricated
  answer. The detailed technical receipt report is preserved unchanged.
- A general factual catalog must not suppress this model synthesis when
  sufficient directly relevant incident events have actually been returned.
- The experimental Native V2 API explicitly enables this feature. Existing
  code invoking the agent directly and production Main Ask stay unchanged.
  This is **independent** of the model's ability to authorize tools: the
  live manifest and executor remain READ-only.

## Truthfulness and limitation

This proof of read receipts is not a mathematical proof of the *English
hypothesis's causal entailment*. Even two authentic source events may admit
several explanations. Therefore the model's interpretation is explicitly
"possible", and diagnostics report
`semantic_entailment_verified=false` and
`root_cause_verified=false`. It does not declare the cause established
from timestamp proximity. Unverified physical facts, such as a user unplugging
a socket, must come from an independent source or a user statement.

This is the **second architectural milestone** in the reasoning redesign;
it does not yet implement a comprehensive hypothesis comparison engine or
establish parity with Claude.

## Validation

`pytest -q tests/test_investigation_v2_model_grounded_reasoning_0_18_230.py`

Unit and end-to-end tests verify a natural incident answer grounded in two
real dated records, block invented events/read IDs, repeated references,
model certainty and invented numerical claims, and ensure source-only
fallback for unsupported prose. Full repository CI and container smoke are
required before merge.

## Next live acceptance

Run a dated lighting or heating incident for which contemporaneous switch,
sensor, app actions and logs are available. The AI should produce a concise
specific explanation **when it can cite appropriate real event evidence**,
otherwise acknowledge exactly what is missing. Evaluate these results
against independently understood household incidents rather than synthetic
unit test pass counts alone.
