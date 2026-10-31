# Hubitat MCP AI v0.18.282 — Stage 4B semantic sufficiency protocol

**Source-only offline protocol, not an active answer or model integration.**

- Adds `stage4_semantic_sufficiency.py`: each Stage 4A typed-valid
  model sentence is reviewed against only its cited host-owned facts.
  Two separately supplied reviewer verdicts can be `entailed`,
  `contradicted` or `insufficient`; schema and fact scope fail closed.
- Adds an offline independently labelled benchmarking interface to
  measure sentence-level **false accepts**, false rejections and
  reviewer concordance without trusting model-supplied confidence.
- Includes 14 constructed positive/counterfactual cases across lighting,
  heating, fan operation, power, source-vs-collector clocks and incomplete
  historical evidence. Also proves that two wrong, agreeing reviewers
  can falsely accept a model's invented cause.
- All externally submitted reviewer assessments and fixture oracle labels
  are explicitly **not independently authenticated**. No real model judge
  has been run or production quality improvement demonstrated.
- Even total reviewer agreement reports
  `independent_semantic_truth_verified=false` and
  `production_publication_approved=false` by construction.

No new network/model/MCP calls, device changes, active planner or publisher
imports, add-on runtime activation, prompts, migrations or logging of user
prose. Existing Stage 4A and original V3 publication remain untouched.

See `docs/INVESTIGATION-STAGE-4B-SEMANTIC-SUFFICIENCY.md`.
Rollback: revert this additive PR.
