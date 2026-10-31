# HomeBrainOS v0.18.287 — Stage 4G full authored answers, actual local models

**Source-only, offline and synthetic; no production publisher or smart-home changes.**

- Adds `stage4_full_answer_evaluation.py`: model-authored natural-language
  sentences are checked for correct source fact-ID references; host-owned
  typed fact projections are separately validated; independent expected
  fact coverage and diagnostic two-reviewer agreements are measured.
- Adds `tools/stage4g_github_authored_answers.py`: actual Qwen2.5 3B
  authored sentences, bounded strict JSON grammar, local Ollama inference,
  a balanced two-reviewer diagnostic, aggregate-only public report.
- Four constructed source questions: lighting, heating, ventilation and
  collector timestamp/history gap. Expected citation IDs never enter
  author or reviewer prompts; raw model prose never enters public CI.
- New read-only, no-cloud, no-secret GitHub Actions workflow on an
  ephemeral CPU runner. Includes adverse citation, unsupported cause,
  malformed model replies, mismatched reviewer, privacy and no-active-
  agent import regression tests.
- **Critical caveat:** A model can make a false causal claim while
  citing a valid source event. Host projected claims are not authored
  assertions; reviewer agreement is not independent truth. No
  independently adjudicated prose oracle or real home event tested.
- Stage 4F actual baseline remains eight constructed sentence reviews,
  with Qwen2.5 3B 0/4 false accepts and 0/4 false rejects, and
  Llama 3.2 3B 3/4 false accepts and 0/4 false rejects.

No live AI routing, original publisher modification, tool/permission
change, new model calls in HomeBrainOS, Hubitat/HA configuration or
upgrade. Existing release behaviour is unchanged.

See `docs/INVESTIGATION-STAGE-4G-AUTHORED-ANSWERS.md`.
Rollback: revert additive source PR or disable its GitHub workflow.
