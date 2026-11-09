# HomeBrainOS v2 alpha.22 — Autonomous First-Answer Lab

**Status:** Isolated, opt-in, **synthetic** model-led MCP evaluation.
**Scope:** The real v2 \`Agent.answer\` code and live skill are reused, but every
MCP tool is served by a new **in-memory fictional MCP server**. It never
instantiates or connects to the live \`MCPClient\`, Hubitat or Home Assistant.
This is an evaluation of first-answer tool selection and interpretation, not
a live device health or control check.

## Why this follows the 10-case fixed-source benchmark

The private A/B benchmark completed **10/10** paired, human-reviewed Gemma
answers on 9 November 2026. The final aggregate difference with generic
source-role notes was approximately **-3** score-points over **46 applicable
comparisons**, distributed across five rating criteria. Baseline and
annotation conditions each won three cases, with four ties. Source completeness
and command verification had no overall improvement, while several answers
overstated causal conclusions. Cases 005/006 repeat the same humidity sequence.
These ratings were informed by assistant feedback, not a second independent
human rater. No general performance improvement was established.

That benchmark always supplied the same frozen evidence and **never tested
autonomous tool selection**. This new lab exercises a separate first-answer
path without using the home's private source history or installing test rules.

## Mobile setup and operation

1. Update only the standalone **Hubitat MCP AI v2** add-on to
   **2.0.0-alpha.22**, restart and open its Home Assistant ingress UI.
2. Choose the new **Autonomous Lab** tab. This is distinct from the
   earlier **AI Benchmark** page; the previous private ZIP and A/B scores
   remain intact.
3. Select one of six completely fictional scenarios. You may read the fixed
   question **without** running the model. No scenario contains a real home
   device ID, IP, token, recorded household events, or an actual hub connection.
4. Review both consent checkboxes and select **Run selected synthetic case**.
   The model will receive a standard v2 hub-skill prompt and an explicit
   fictional-sandbox notice. It chooses native-shaped MCP gateway tools and
   arguments autonomously. **Even if it calls a device-command tool**, that
   call only changes an in-memory simulated device. There is no forwarding
   path to a live hub. The model may use Ollama Cloud credits; do not run
   without accepting those terms.
5. The evaluator limits a run to **8 model rounds**, **24 synthetic MCP
   calls**, and a **90-second investigation deadline**. Stop cancels the
   model task. Completed results persist under
   \`/data/homebrain-v2-autonomous-lab\`; a completed case is never overwritten
   automatically. There is no scheduled, automatic or background-on-start
   model invocation.
6. Examine the model's first answer, exact synthetic tool receipts, the
   required **read-source coverage checklist**, retry/blocked-attempt counts,
   round count and time.
7. Score factual grounding, source completeness, causal calibration,
   command outcome and usefulness **manually** on 0/1/2/n/a. In read-only
   cases, command outcome may genuinely be n/a. A tool call being present
   or successful does not mean the model's conclusion is correct.
8. Export the aggregate report. It excludes source data, prompt text,
   answers, tokens and credentials, but includes per-case coverage, model
   rounds, simulated actions, blocked attempts and manual ratings. Download
   the JSON and discuss it separately from the private A/B report.
9. Use **Clear synthetic results** to remove these six local case outputs and
   scores. The previous private fixed-source benchmark remains untouched.

## Case bank (fully fictional and distinct from the private benchmark)

| Scenario | Primary quality gate | Safe test condition |
| --- | --- | --- |
| \`lab-01\` — Bench Study Lamp | Exact target, simulated brightness command, **fresh independent level and switch reads**, no physical success claim | Memory-only \`setLevel(40)\` |
| \`lab-02\` — Bench Workshop Fan | Command accepted but independent read still OFF; **no command retry** | One memory-only \`on()\` |
| \`lab-03\` — Bench Boiler and zones | Historical state/setpoint reads for each zone, absence of records for one zone | Read-only |
| \`lab-04\` — Bench Air Extractor | Correlate schedule, command source and humidity; distinguish strong timing from a proven internal trigger | Read-only |
| \`lab-05\` — Bench Cellar Sensor | Stale-activity threshold vs confirmed outage; limited log coverage and MQTT attribution | Read-only |
| \`lab-06\` — Bench Corridor Lamp | Bridge-reported OFF, downstream listener vs actual command issuer; missing issuer evidence | Read-only |

## Architecture and safety boundaries

- **No production Agent change.** \`BoundedAgent\` reuses the exact production
  \`Agent.answer\` and \`Agent.round\` implementations; its only model-side
  difference is an evaluation-only hard limit on rounds and elapsed time.
- **No live MCP reference is passed.** \`SyntheticMCP\` is the only argument
  passed as the agent's \`mcp\` parameter. It implements a small fictional
  \`tools/list\` and native-shaped gateway catalog; it stores all simulated
  state strictly in memory. It imports no Hubitat connector.
- The model may discover fictional read gateway leaf schemas and may call a
  fictional management gateway, but the adapter **denies all writes** except
  the single explicitly allowed simulated action in \`lab-01\` and \`lab-02\`.
  Duplicate actions and mismatched targets/arguments are denied and counted.
- A successful synthetic command acknowledgement is intentionally separate
  from its pre-command snapshot and from subsequent independent reads.
- The evaluation automatically checks **which source classes were actually
  retrieved**, not whether the resulting prose is true. Manual independent
  assessment is still necessary to classify causal overclaims, outdated
  snapshots and missing physical confirmation.
- Case fixtures do not include production household records, gateway IPs,
  real device identifiers or actual secrets. The model client uses the
  configured v2 model endpoint, and remote/cloud transfer of synthetic data
  requires explicit consent. The page includes no native hub-control buttons.
- Evaluation results are stored under the add-on's private \`/data\` directory
  with 0600 files and a private parent directory. The ordinary app cache
  policy remains \`no-store\`.
- Only six known local result files and six rating files are eligible for
  deletion. No live hub, installed automation, recorder or user-source file
  is read or changed by this evaluator.

## Acceptance and limitations

Tests run scripted LLM responses through the **real** \`Agent.answer\` loop
against the synthetic gateway, checking automatic tool selection, fresh
read-after-command, denied repeats and failure safety. Separate API tests
ensure consent precedes any model request; browser smoke checks desktop/mobile
tab operation, report export and HTML-safe text presentation. All tests
are **synthetic** and incur no cloud credits.

This provides a repeatable sandbox for evaluating **autonomous planning** in
a safe environment. It is not proof of physical command outcomes, successful
live Rule Machine creation, response quality on unseen household incidents, or
hub uptime. Do **not** change live agent reasoning or device-control semantics
based only on synthetic scenarios. Review real, consented, read-only
investigations separately, and retain explicit approval for future writes.

**Rollback:** install alpha.21. Synthetic results persist in add-on \`/data\`
until deleted explicitly in alpha.22. No change to V1 or other services.
