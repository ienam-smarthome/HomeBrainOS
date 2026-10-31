# HomeBrainOS v0.18.288 — Stage 4H real-reviewer, complete-answer references

**Source-only offline benchmark, not a live add-on update or publisher switch.**

- Adds `stage4_full_answer_reference.py` to compare all sentences of
  complete pre-authored synthetic explanations with independent
  fact-coverage expectations and curated reference judgments.
- Eight multi-sentence answers across lighting, heating, ventilation,
  and contact/history: four adequate, three containing an invented
  cause, and one true but incomplete because it omits a documented gap.
- The read-only, no-secret GitHub CPU workflow executes Qwen2.5 3B
  and Llama 3.2 3B as locally resident, no-cloud semantic reviewers;
  expected reference labels and coverage sets are withheld from models.
- Aggregate metrics separately count per-model false acceptance,
  false rejection, incomplete-answer acceptance, adequate answer
  rejection, and reviewer disagreements. Invalid or incomplete reviews
  are *unscored*, never silently treated as correct.
- These are **host-curated, pre-authored** answers. This does NOT
  independently score newly generated Stage 4G prose, authenticate
  human labels, prove Claude-level usefulness, or authorise publication.
- No changes to the active HomeBrain agent, MCP tools, app routing,
  system logs, Home Assistant/Hubitat, models selected in production,
  or the existing V3 final publisher.

See `docs/INVESTIGATION-STAGE-4H-FULL-ANSWER-REFERENCES.md`.
Rollback: revert the additive PR or disable the Stage 4H workflow.
