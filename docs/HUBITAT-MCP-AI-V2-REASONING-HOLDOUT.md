# HomeBrainOS v2 alpha.25 — Blinded reasoning-quality holdout

## Purpose and prior evidence

The user completed two separate evaluations on 9 November 2026:

- **Fixed frozen-source A/B**: 10 paired questions with generic source annotations
  versus baseline. Three wins each and four ties; annotations had no clear
  aggregate benefit, and repeated humidity cases limit independence.
- **Autonomous fictional MCP pilot**: Six different standalone fictional
  scenarios with a model selecting native-shaped tools. All six model runs
  completed and were rated. Read-source retrieval was **19/22 (86.4%)**,
  whereas manual answer-quality scores totalled **34/52 (65.4%)**. The
  weakest rated dimension was causal calibration (**5/12**). Human scores
  were informed by ChatGPT's reviews, not blind external raters.

These small, selectively designed samples do not prove how Gemma performs on
unseen household events. The six previous autonomous trials are **not used**
as the candidate's evaluation data. Nor does this experiment change any
installed native MCP command, Home Assistant integration, or live model
reasoning.

This milestone tests one **general candidate intervention**: an additional,
short system-level *investigation completion audit* encouraging evidence
completeness and hypothesis discrimination. The baseline is **exactly the
existing v2 Agent.answer / Agent.round tool-use loop with the existing
production system skill**, without that extra audit. The candidate uses
exactly the same tool loop and model endpoint with only that appended
evaluation-only guidance. The full candidate text is in
\`rootfs/app/reasoning_experiment.py\`; it does not select tools, force
additional calls, hard-code outcome rules, or grant any control privileges.

## Mobile operation

1. Update **only the Hubitat MCP AI v2 add-on** to **2.0.0-alpha.25**, then
   restart the add-on. The previous private A/B score archive, the six-case
   Autonomous Lab results and Hub Diagnostics remain untouched.
2. Open its Home Assistant ingress page and select **Reasoning A/B**.
3. Select one of **six new, fictional holdout cases**. The question is
   visible before starting; each scenario uses made-up \`HOLD-...\` IDs.
4. Approve the two model/cloud consent checkboxes and select **Run blinded
   A/B pair**. It runs one model session per arm, **sequentially**, with the
   same fixed question, same configured model and a fresh isolated in-memory
   MCP fixture. Neither arm can access a real Hubitat or Home Assistant.
5. Review both answers and their tool receipts without attempting to deduce
   which arm is baseline. Each arm displays actual retrieved source checks,
   model rounds, time, client-side schema errors, simulator rejections and
   memory-only commands.
6. Rate both independently on **factual grounding**, **source completeness**,
   **causal calibration**, **command outcome** and **usefulness** (0, 1, 2
   or n/a). A read-only retrospective investigation may legitimately have
   command outcome = n/a.
7. Save the blind ratings. Repeat for the other five cases. The hidden
   condition mapping is not returned by the UI API or aggregate report
   until **all six pairs are completed and rated**.
8. Download the final **aggregate report JSON**. Only then does it provide
   condition labels, paired score differences and per-criterion mean effect.
   The export omits prompts, raw answers, original tool receipts, private
   allocation files and configured model credentials.
9. If a model run fails or is stopped after one arm finishes, completed arm
   evidence is retained. Restarting that case continues the unfinished arm;
   a previously failed arm requires a separate consented retry. Up to two
   failed attempts per arm are preserved. Successful/rated arms never get
   silently rerun. Explicit deletion removes **only the new reasoning A/B**
   experiment files.

**Cloud credits:** One completed case uses at least two actual model
requests, often more because the agent autonomously discovers native-shaped
tools. Each arm has an evaluation-only cap of 12 model rounds, 40 synthetic
tool attempts and a 120-second deadline. Start one pair at a time; actual
Ollama Cloud costs depend on the connected account and token usage. No model
calls happen merely because the interface is opened or a case selected.

## The new six-case holdout bank

| Case | Fictional task | Important distinction |
| --- | --- | --- |
| \`hold-01\` | Freezer plug's low-power interval | 0 W consumed does not prove lost electrical supply, and discrete observations do not establish duration |
| \`hold-02\` | Entrance lamp with app command and downstream listener | Bridge event reporter vs listener vs direct command issuer; timing supports but does not fully trace controller internals |
| \`hold-03\` | Workshop humidity sample crossings | First observed above threshold vs exact crossing; interval of samples and unrelated ventilation state |
| \`hold-04\` | Central heater and three zones | Historical main operating state and setpoint, multiple room demand histories, and absent zone events |
| \`hold-05\` | Nursery and roof stale sensors | Two old reports and bounded logs do not prove a common MQTT/power/network outage |
| \`hold-06\` | Accepted beacon ON command | Acknowledged action, independent read still OFF, no duplicate command and no physical proof |

The bank is intentionally fictional and separate from the previous six
scenarios; the model is never shown a correct answer or scoring rubric during
a run. The user question must still not be considered proof of any event.

## Blinding and experimental safeguards

- The first time a case is run, a hidden A/B assignment is created with
  operating-system cryptographic randomness and stored in a private
  \`/data/homebrain-v2-reasoning-ab\` file. Each arm starts with fresh
  \`SyntheticMCP\` state and an empty conversation history. The generator
  runs the same \`Agent.answer\` and the same tool gateway schema in both
  arms. Only the candidate's first system message has the extra prompt.
- A report exported **before** all six pairs have blind ratings contains
  case labels A/B, source coverage and scores, but **never the condition
  mapping**. After full scoring, the mapping and differences are revealed.
- The candidate text is **general**: source interpretation, relevance of
  discriminating read-only checks, alternative explanations, bounded-history
  gaps and appropriate uncertainty. No case-ID-specific patches, hard
  evidence gates, command-specific overrides or deterministic forced tool
  paths are introduced.
- The fake server is injected as a plain \`SyntheticMCP\` object. It does
  **not** instantiate the real MCPClient or look up an HA/Hubitat endpoint.
  Five holdout scenarios disallow commands altogether; the one command
  scenario accepts only one exact in-memory ON operation, and refuses any
  repeat or different target.
- **Dashboard error accounting:** Legacy Autonomous Lab and new paired
  experiment now distinguish \`client_contract_errors\` (rejected by the
  agent before execution), \`simulator_rejections\` (fake MCP server rejection)
  and other failed calls. The earlier "0 blocked" reading could coexist
  with an actual client schema-validation error. These fields do not
  indicate physical control.
- The model endpoint is the configured v2 Ollama connection. Remote/cloud
  use requires user consent. Raw answers and synthetic receipts stay in
  private add-on storage; no household file or original A/B evidence is
  imported.

## Interpreting the result

The primary proposed measure is blind manual **causal-calibration quality**,
followed by grounding, source completeness, command outcome and usefulness.
Secondary measures are whether the agent retrieved the discriminating tool
sources, contract errors, attempts and elapsed time. The conditions may have
unequal tool counts and duration: that is an observed tradeoff, not a reason
to re-run until a desired result appears.

The sample contains only six fictional paired cases, and any judgement
made by a single evaluator informed by the earlier benchmark is not
independent. If the candidate appears promising, run a separate **new,
unseen** read-only real-world acceptance study before proposing promotion.
Do not modify live reasoning, device-control permission, native rules,
existing dashboards, or the earlier benchmark based on this study alone.

The build/CI uses fully mocked model HTTP requests. It verifies that the
candidate receives only its extra general system guidance, the baseline
does not, each arm has fresh in-memory MCP state, no real device actions
occur, retries preserve results, blind mappings stay hidden and aggregate
exports contain no raw source evidence. These tests are **not** actual
Gemma inference: the first model-led evaluation happens only when the user
explicitly runs the paired test in the installed add-on.
