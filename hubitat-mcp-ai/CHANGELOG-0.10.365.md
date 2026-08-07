# Hubitat MCP AI 0.10.365

## Fixed

- **The 0.10.364 article fix was incomplete -- short device labels still
  failed.** "turn off the fridge" was fixed in 0.10.364 by excluding
  "the"/"a"/"an" from the specific-token compatibility check, but that
  only capped how far a match could be *penalized* by the article -- the
  article's literal characters were still part of the string fed into the
  underlying `SequenceMatcher` similarity score. For a long label like
  "Fridge" that was enough to stay above the confidence floor (0.8), but a
  live retest immediately surfaced the same failure on a short label:
  "turn off the TV" scored only 0.57 against "TV" (3 extra characters of
  "the" dominating a 2-character label) and fell below the floor exactly
  like "the fridge" had before. Fixed properly this time, at the root:
  `device_target_resolver.py`'s shared `_plain_text()` normalizer now
  strips a leading English article before any scoring happens at all, so
  "the tv" and "tv" are now identical strings from the very first
  comparison -- both cases now resolve as clean, top-confidence exact
  matches (1.0) rather than one of them merely surviving a lower-tier
  fallback. The earlier specific-token exclusion is left in place too, as
  defense in depth for non-leading occurrences.
- **Power-usage questions still summed monitored smart-plug wattages
  instead of reading the whole-house meter, even after 0.10.364.** That
  release fixed the underlying data-visibility gap (the meter's reading
  was invisible everywhere due to a `valueStr`-only attribute shape), but
  a live retest showed the model was still producing the same wrong
  answer -- the actual blocker was tool selection, not data visibility:
  the aggregation path only ever considers switch-capable devices, and
  the whole-house meter isn't one (no Switch/Actuator capability), so it
  was structurally excluded regardless of whether its data was visible.
  Added explicit system-prompt guidance in `agent_prompt_policy.py`
  directing whole-home power/energy questions to look for a single
  dedicated meter device first, and to only fall back to summing
  monitored plugs -- with that limitation stated explicitly -- when no
  such meter exists in the home's inventory at all.

## Context

Both fixes came from live retesting immediately after 0.10.364 shipped:
"turn off the TV" reproduced the same class of bug as "the fridge" had
(same root cause, different severity by label length), and "what's my
current power usage" still returned the same wrong total as before
0.10.364, proving that release's fix, while correct as far as it went,
had not addressed the actual blocker for that specific bug.

## Validation

- `python -m pytest -q` -- 608 passed, including
  `test_leading_article_on_a_short_label_does_not_sink_below_the_floor`
  (new) and a strengthened
  `test_leading_article_is_stripped_before_scoring_for_a_clean_exact_match`
  (now asserts a clean 1.0-confidence exact match, not merely a passing
  resolution).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.365.
- `python scripts/analyze_imports.py` -- zero orphan modules.
