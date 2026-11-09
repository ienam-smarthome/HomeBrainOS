# HomeBrainOS v2 — blinded fixed-source A/B benchmark

**Established:** 8 November 2026. **Installed/runtime baseline:** 2.0.0-alpha.18, unchanged. **Experiment status:** synthetic harness implemented; model responses have not yet been run or graded.

## Question

First-answer reviews across ventilation, humidity, lighting, heating, stale-device telemetry and ordinary actions reveal a recurring distinction between retrieving useful MCP evidence and drawing a supported conclusion. We want to test whether generic source-role presentation helps the same model interpret the same evidence more accurately, *without* adding domain-specific patches or changing native tool routing.

This experiment compares **source interpretation, not autonomous tool selection**. It deliberately uses a retrospective offline transcript; the benchmark never executes commands or calls a model.

## Available private evidence

The user's 18 Technical JSON exports were inventoried locally without publishing them. Ten have no prior source context reported and contain at least one fresh successful source receipt; eight report prior evidence and are excluded from the self-contained pair. The eligible cases cover multiple domains, but some concern related questions and are not independent household/device samples.

| Observational group | Cases | Median browser response | Native attempts |
| --- | ---: | ---: | ---: |
| No prior source context reported | 10 | 12.406 seconds | 52 |
| Prior context reported | 8 | 7.813 seconds | 20 |

These are different tasks, not a controlled latency comparison. No original AI answer is automatic ground truth.

## Conditions

The local tool at hubitat-mcp-ai-v2/tools/fixed_source_benchmark.py freezes the same recorded question and exact native MCP response strings in paired A/B files.

- **Baseline:** Original native response strings, arguments, call order, failures and statuses as exported.
- **Role notes:** The *identical* source receipts and instruction, adding generic provenance notes per call. Examples: command submission versus state report; bridge reporter versus command issuer; returned event rows versus complete history; current app configuration versus past internal decisions; and bounded latest log page versus absence of errors.

The original model answer is intentionally **not included**. The source SHA-256 is the same in both conditions and is rechecked before reporting. The A/B assignment is deterministic and balanced, with the unblinding map in a private manifest. Different evidence or different instructions invalidate the pair. Notes add no fresh measurements or incident-specific conclusions.

## Private setup

Use a private folder **outside the Git repository**, and supply the previously exported local Technical JSON files:

~~~powershell
python hubitat-mcp-ai-v2/tools/fixed_source_benchmark.py prepare --out "$env:USERPROFILE\HomeBrain-v2-fixed-source-private" --seed 42 "C:\Private\Exports\first.json" "C:\Private\Exports\second.json"
~~~

The folder must not already exist. Source bundles and answer files contain private home/device data. Do not commit, send to GitHub issues/CI, publish, or upload the raw files to another service without a deliberate privacy decision. The tool sets restrictive POSIX permissions; protect Windows ACLs as appropriate.

For each case, give A and B to **the same model** in independent fresh conversations, with no MCP connection, identical sampling settings, and sufficient context capacity. Save *unaltered* model answers in the generated answers folder and record model timings if measured. Use the private, blinded ratings template to assess each answer on a 0/1/2 scale (or n/a) before inspecting condition assignments:

1. factual_grounding — whether claims match source facts;
2. source_completeness — missing members, attributes, time windows and reads;
3. causal_calibration — source vs hypothesis, no unsupported internal mechanism;
4. command_outcome — accepted call, reported state and physical effects separated;
5. usefulness — answers or precisely identifies missing discriminating evidence.

Rating 0 means unsupported or incorrect, 1 partially useful or overconfident, 2 supported and adequate. n/a is for genuinely inapplicable dimensions. A missing rating is **not** a pass.

When both paired answers and blinded ratings exist:

~~~powershell
python hubitat-mcp-ai-v2/tools/fixed_source_benchmark.py report --directory "$env:USERPROFILE\HomeBrain-v2-fixed-source-private" --output "$env:USERPROFILE\HomeBrain-v2-fixed-source-review.json"
~~~

The output contains aggregate counts, paired role-notes-minus-baseline rating differences, better/tie/worse counts, latency differences when supplied, and missing-answer/rating counts. It does **not** automatically grade correctness. Zero fully reviewed pairs means *pending*, not a model result.

## Release gate

Interpret improvements only after paired, source-reviewed examples across more than one independent domain. Account for context length, order effects, case dependence and measured latency. Do not infer population accuracy from this purposively selected set. If a promising general source-presentation approach emerges, consider a **separate runtime PR** with unchanged original MCP payloads and its own live read-only first-answer acceptance.

Do not add a fixed planner, tool-use restriction, answer rewriting, automatic write retry, physical-actuation claim, heating-specific workaround or unverified permission preflight. Supervised write testing requires explicit user authorization and device safety checks.

**Rollback:** remove this offline tool, its synthetic tests and docs. Hubitat, Home Assistant, installed alpha.18, Gemma, the native MCP server, independent recorder and V1 are unaffected.

## Optional local Ollama pair runner — explicit opt-in

The companion tool at hubitat-mcp-ai-v2/tools/run_fixed_source_pairs_ollama.py
submits frozen retrospective A/B prompts to the user's running Ollama
instance through the local /api/chat endpoint, with one independent,
tool-free model conversation per variant. It cannot call Hubitat or MCP.

**Privacy warning:** A model whose name contains "cloud" (such as
gemma4:31b-cloud) may forward raw private MCP source evidence from local
Ollama to the cloud provider. You must explicitly approve this transfer
and any cloud usage cost before running the pilot. No data is transmitted
by the default dry-run. The flags --run and --acknowledge-private-mcp-data
are both required to send anything. Cloud models also need
--allow-cloud-model. Non-loopback endpoints require explicit
--allow-remote-endpoint and HTTPS. Credentials in endpoint URLs are rejected.

Unzip the private benchmark bundle OUTSIDE the Git repository, then preview
the number of planned requests without any network traffic:

~~~powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\HomeBrain_v2_FIXED_SOURCE_PRIVATE.zip" -DestinationPath "$env:USERPROFILE\HomeBrain-v2-fixed-source-private"
python hubitat-mcp-ai-v2/tools/run_fixed_source_pairs_ollama.py --directory "$env:USERPROFILE\HomeBrain-v2-fixed-source-private" --max-pairs 2
~~~

After expressly approving the private source transfer to your existing
Gemma cloud model, run a **two-pair pilot**:

~~~powershell
python hubitat-mcp-ai-v2/tools/run_fixed_source_pairs_ollama.py --directory "$env:USERPROFILE\HomeBrain-v2-fixed-source-private" --model "gemma4:31b-cloud" --max-pairs 2 --run --acknowledge-private-mcp-data --allow-cloud-model
~~~

Only after inspecting pilot results and cloud usage, use --max-pairs 10
to complete the ten-case sample. Existing answer files are skipped and
never overwritten; elapsed model time is written beside the still-empty
blind rating fields. A/B execution order is randomised while system/user
context and model settings are identical. No MCP tools or write functions
are passed to Ollama. The script does not score model answers or measure
physical device outcomes.

For a purely local model, substitute its installed ID and omit
--allow-cloud-model. This compares a **different model** rather than the
original cloud Gemma. No automatic provider fallback or extra API key
configuration is provided. Failure to contact Ollama or a returned model
tool-call is an error rather than a fabricated success.

After independently grading each paired answer *blindly*, use the
fixed_source_benchmark.py report command above. Generated prompts, model
answers, timings and condition maps remain private. Synthetic CI success
does not demonstrate actual model answer improvement.
