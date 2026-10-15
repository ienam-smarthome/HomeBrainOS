# HomeBrain v0.17.72 — Evidence-first causal answer selection

## Live regression resolved in code
v0.17.71 collected the source-typed preceding command and intervening OFF event, but its model sometimes declared an external Hue initiator anyway. This revision treats a unique, verified focal ON event with an exact-target preceding Hubitat command and no proven delivery chain as a **structured investigation outcome**, not unrestricted model prose.

- New reusable `skill_grounded_answer.py` produces a grounded leading-command explanation from receipts, including command timestamp/delay, intervening states, reporting integration, any checked sensors, source checks, competing explanations and decisive read-only next checks.
- `FinalAnswerCoordinator` uses this result **instead of calling the final model** only in this narrow, objectively supported circumstance. This avoids repeated literal phrase repairs and should reduce model rounds. Other causal paths retain established model validation and fallback.
- The existing general hypothesis layer no longer hardcodes Hue in generic alternatives.
- Adds actual coordinator integration regression: a model intentionally raising an error must never be called for this matched verified case. Tests also cover irrelevant/unmatched command, OFF requests and differently named reporting bridges.
- New `skills_grounded_answer_selected` privacy-safe diagnostic counter.

## Safety and limits
Read-only; no Hubitat modifications. The recorded command is **not** declared proven causation. Source-side MQTT/touch, transport acknowledgement and bridge-side command logs remain material historical gaps. Model performance improvement and live correctness must be checked after add-on upgrade.
