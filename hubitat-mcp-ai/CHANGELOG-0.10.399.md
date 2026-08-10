# 0.10.399

## Why this release

Fourth and final of four grouped releases closing Tier 2 findings from
the proactive full-codebase review conducted earlier this session
(release 1, 0.10.396: device-classification/tool-success consistency;
release 2, 0.10.397: write-safety gating for the two direct
`hub_manage_*` tools; release 3, 0.10.398: pagination cap and
token-estimator robustness). This release closes a phrasing gap in two
deterministic intent parsers.

## Fixed

**Apostrophe-free "whats"/"hows" phrasing wasn't recognised for hub
health or firmware status questions.** `contextual_read_fast_path.py`'s
device-attribute question parsers already accept the apostrophe-free
contraction spelling a mobile keyboard's autocorrect or a fast typist
commonly produces -- `what(?:'s|s|\s+is)` matches "what's", "whats", and
"what is" alike. `request_classification.py`'s
`parse_hub_health_intent`/`parse_firmware_status_intent` never got that
same treatment: their regexes only matched `what(?:'s|\s+is)` and
`how(?:'s|\s+is)`, so "Whats the hub health status?" or "Hows the update
going?" fell through to the free-text model loop instead of routing to
the deterministic, unit-safe snapshot path both of these intents exist
to guarantee. Both regexes now accept the same `what(?:'s|s|\s+is)` /
`how(?:'s|s|\s+is)` alternation already used for device-attribute reads.

## Validation

- `python -m pytest -q` -- 725 passed (existing
  `test_firmware_status_intent_matches_only_progress_questions` and
  `test_hub_health_intent_matches_the_webui_button_text_and_close_variants`
  extended with apostrophe-free assertions: "Hows the update going?",
  "Whats the hub health status?", "Hows the hub health?", "Hows the hub
  doing?" -- all now route to their deterministic intent as expected).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.399
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes finding #13 from the full-codebase review
  conducted this session (Tier 2), completing all six Tier 2 findings
  scoped into this round (#9-13, #15). Finding #14 (content-blind
  evidence grounding) remains an open architectural discussion item, not
  scheduled into any release. Tier 3 findings (#16-20) were out of scope
  for this round.
