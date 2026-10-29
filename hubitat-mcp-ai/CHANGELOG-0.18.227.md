# Hubitat MCP AI v0.18.227 — AI-led intent interpretation for native V2

## Live cause and architecture defect

The v0.18.226 read-only live question was rejected before the model or
Hubitat MCP ran. The legacy shared control parser treated the hyphenated
noun `switch-state` after a comma as an independent `switch` command,
despite the full question being an explicitly no-write investigation.

Fixing that one word would not solve the general issue: a lexical gate
cannot safely decide the intent of arbitrary investigative questions.

## Architecture

- **Native Investigation V2:** remove its keyword-based, pre-AI
  write-intent admission gate entirely. Every authorised user question
  reaches the existing model's **first planning call**, with no extra
  classifier-model request or additional provider billable call.
- Include a host-local `homebrain_request_main_ask` navigation-only tool
  alongside the independently validated MCP READ tools. The model decides
  from the *whole request* whether to investigate or hand off an affirmative
  request to change Hubitat state.
- When the model chooses handoff, the host returns the familiar 409
  `v2_control_not_supported` with a Main Ask navigation option.
  The local tool has no MCP execution or write authority.
- **Security boundary is separate from natural-language intent:**
  the native tool manifest includes only vetted READ endpoints; the
  executor rejects any other tool effect, disallowed arguments or unverified
  IDs. Even a wrong AI intent decision can never authorise a Hubitat write.
- **Legacy V2 A/B baseline:** retains its historical preflight and
  direct control rejection. Improve the shared helper's hyphenated-word
  grammar so `switch-state`, `switch-level` and similar nouns no longer
  masquerade as independent imperative clauses.
- Production Main Ask/control permissions and confirmation remain unchanged.

## Verification

`pytest -q tests/test_investigation_v2_ai_intent_boundary_0_18_227.py`

This includes the literal 29 October Bedroom 3 Mesh screenshot question,
explicit actions, model-selected first-call handoff without any MCP reads,
model-selected normal read for a historical question, and HTTP admission /
control handoff. Existing READ-only and unauthorized write tests continue.

## Important limitation

AI interpretation is not infallible. It may choose the Main Ask handoff
for some legitimate investigations, or attempt unrelated READ operations
for a direct-control question. Such errors are detectable and can be
improved using live tests, but *cannot cause writes* through this endpoint.
This change removes the architectural source of **pre-model keyword denial**,
not every possible future model misunderstanding.

## Repeat live test

Use the exact same screenshot question after updating to v0.18.227.
Expected: the Native MCP read agent should be invoked; no
`v2_control_not_supported` due to `switch-state`. For genuine direct
control requests, the model should choose the local Main Ask handoff,
with zero MCP reads and no device changes.
