# Hubitat MCP AI v0.18.284 — Stage 4D offline answer comparison

**Source-only milestone, not a live deployment or publisher activation.**

- Introduces `stage4_offline_answer_comparison.py` to compare a
  provided incumbent HomeBrain answer with a model-authored Stage 4A
  candidate, grounded in the same bounded source packet.
- Separately reports exact typed claim validity (Stage 4A), two-reviewer
  semantic concordance (Stage 4B) and supplied post-hoc preferences
  for factual fidelity, question coverage, causal calibration, clarity
  and actionability. No fixed room/incident strings decide a winner.
- Adds opt-in, local-only `tools/stage4d_local_answer_compare.py`
  with 512-KiB private JSON input limit, mandatory acknowledgement,
  no model/network/MCP/device calls and aggregate-only output.
- Adds cross-domain constructed scenarios, malformed/secret-bearing
  source rejection, incomplete-review and missing-adjudication tests.
- Supplied reviewer responses and quality labels cannot independently
  authenticate semantic truth, blind raters, or justify replacement.
  Every run returns `winner_selected=false`,
  `publisher_replacement_authorised=false`,
  `production_answer_changed=false`.

No changes to the live agent, V3 publisher, feature flags, prompts,
models, device controls, Hubitat or Home Assistant. Stage 3F local
capture remains default OFF. Genuine Stage 4C local inference results
have not been captured in this PR.

Details: `docs/INVESTIGATION-STAGE-4D-OFFLINE-ANSWER-COMPARISON.md`.
Rollback: revert the additive PR; no live state to undo.
