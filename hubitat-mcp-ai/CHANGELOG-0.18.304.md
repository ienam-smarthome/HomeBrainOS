# HomeBrainOS v0.18.304 — Stage 7.2: independent question-to-answer coverage

**Experimental, synthetic-only, no production publisher or live-device changes.**

## Why this is needed

The user's real Gemma Cloud tests in the difficult **two competing commands** case found 3/3 relevant sources, 3/3 expected typed findings, and 11/11 correctly quoted source-field values. Yet its prose listed the Inactivity App OFF command, Button App brightness command and OFF report without directly stating whether the OFF report could identify *which app caused the state*. It also said neither command "received a physical acknowledgement" without limiting that conclusion to the inspected records. The evidence and citation scores passed, while the original causal question was only indirectly addressed.

This release measures answer completeness separately from source discovery, typed citations and source values. **Do not increase those existing scores merely by adding more fields.**

## Changes

### 1. General direct-answer requirement (no case-specific final paragraphs)

The existing Stage 6 fictional **final model prompt** now says to answer *the original question* directly, not simply recite a timeline; if a unique cause or physical effect is not supported, clearly say it is not established **by the inspected records**, state what is unresolved and avoid global-negative assertions. The answer remains wholly model-authored. Its existing v2 citation/value JSON schema is unchanged, so it does not require a new token-heavy response format or extra Ollama Cloud request.

### 2. After-run, independently held obligation rubric

New \`stage72_answer_coverage.py\` defines a **post-run benchmark reference** for all three existing fictional incident types. For each incident, the rubric identifies the material parts of the original question: sequence/observations, recorded commands, explicit causal attribution or non-attribution, and limits of physical confirmation.

Each obligation exposes to the **human reviewer only after the model has finished**:

- The expectation to be independently reviewed in the final explanation.
- The relevant fictional evidence record IDs, which ones the model inspected and which it cited.
- Any reference evidence it never inspected.
- A manual **Not reviewed** judgment by default, with options for answered, explicitly unresolved, omitted, overclaimed or unclear.

The host does not use its reference obligations to select sources, write final paragraphs or generate follow-ups. Citation overlap is a limited provenance observation, **not** proof that the prose conveyed an obligation or that a causal conclusion is correct.

### 3. Review UI and export

A nested **Stage 7.2 · Did the answer resolve the actual question?** section appears inside Stage 7 after a successful synthetic Stage 6 run. It shows the original question and obligation-specific evidence IDs alongside independent ratings. Export through **Copy independent review packet** includes the optional manual ratings. A case cannot be declared *independently reviewed by human* unless the new ratings as well as the original sentence/scope/cause ratings are actually completed. It never automatically marks any obligation satisfied.

### 4. Regression boundaries

Mock-only tests demonstrate that an answer with **3/3 expected finding types and all correct atoms** can still omit an explicit answer to the causal question. Other cases check evidence Gemma skipped, unverifiable universal negative claims, invalid source IDs, prompt/reference isolation and zero additional cloud calls. No household devices, real user histories or secrets are involved.

## Important limits

- The human-review rubric is benchmark-specific and **revealed after** the model has finished; it is NOT a general, automatically verified natural-language reasoner or a production hardcoded answer list.
- It does not claim Claude-equivalent prose or certify all implications. The actual improvement to Gemma's answers **must be measured in a fresh real Ollama Cloud test**; mock tests only prove the evaluation machinery.
- This does not automatically rewrite the final answer, override model evidence selections, replace the production publisher, read Hubitat/HA or affect any automations.
- Stage 7.2 itself makes no model calls. Stage 6 remains explicitly consented, with at most four existing-account cloud requests per run; CI uses only mocked transports.
- Roll back by reverting this PR and restoring v0.18.303.

## First manual test

Update the Home Assistant **Hubitat MCP AI** add-on to **v0.18.304**, then run **Stage 6 → Two apps issue competing commands** once with explicit cloud consent. In the generated answer check whether Gemma **explicitly says the OFF report does not establish which application caused the light to turn off**, and whether missing physical acknowledgements are limited to the examined evidence. Open **Stage 7 → Stage 7.2** to independently evaluate each requirement and share the outcome. The goal is direct, well-calibrated natural language, not artificial score inflation.
