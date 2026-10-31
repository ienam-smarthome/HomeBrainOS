# HomeBrainOS v0.18.295 — Stage 6 adaptive conflicting-evidence pilot

**Experimental / synthetic-only / unchanged production publisher.** This builds on Stage 5, which selected up to two fictional sources before an independently authored answer. Stage 6 adds repeated decisions after seeing evidence and deliberately contradictory observations.

## The new benchmark

In the existing HomeBrain UI, expand **Stage 6 · Conflicting evidence** and choose one of three wholly fictional scenarios:

- **Delayed bridge OFF versus device timestamps:** a stale OFF report is delivered after a newer ON report, and a brightness command appears nearby. Collection order is not device event order.
- **Competing applications:** two different applications issued opposing commands just before an OFF report. Issued commands alone do not prove which caused the state report or what the hardware did.
- **MQTT driver connected, mesh plug offline:** the driver's broker session differs from the plug's actual last device telemetry; a scheduled OFF command occurs nearby but causal attribution remains unproven.

The real configured Ollama Cloud model receives a fictional initial observation and source **titles only**, then chooses to READ one source or STOP. It reconsiders after each source, up to **three separate read decisions**, then generates a concise final answer. Up to **four cloud calls** occur per explicitly consented test; a premature stop is scored as a missed relevant source. The cloud model is never given the gold answer or required source-ID set.

## Evaluation dimensions

1. **Source discovery and stopping:** the host keeps withheld reference-relevant source IDs, scores missed sources, irrelevant choices, premature stopping and actual number of reads.
2. **Evidence conflict:** host checks a specific inversion of source event-time versus collector receipt-time from two independently presented records; competing commands require distinct recorded issuers and actions. Mere observation of clocks or app configuration cannot establish cause.
3. **Sentence-level typed source checks:** each generated sentence must declare a claim kind and exact cited record IDs. The host checks record type and required fields, rejects unknown/duplicate citations, and reports unsupported/high-risk labels separately.
4. **Human-readable answer:** the complete model-authored text, uncertainties and proposed next evidence are displayed for independent human inspection. No rewrite of the production answer is performed.

**Important limitation:** These checks cannot certify all claims in arbitrary prose. A sentence may carry multiple unlabelled implications while the model attaches one legitimate claim type. No automated score, even 100%, authorises replacing the current publisher or proves Claude-equivalent reasoning. An independent exhaustive human or independently referenced semantic review is still required.

## Running from a phone

1. Update the Home Assistant **Hubitat MCP AI** add-on to v0.18.295 and open its existing dashboard.
2. Expand **Stage 6 · Conflicting evidence** and choose **Delayed OFF report versus device time** first.
3. Tick the clear confirmation for **up to four Ollama Cloud requests** charged against the existing primary account allowance.
4. Tap **Run adaptive investigation** once. Read the explanation, source selections, expected-finding coverage and source-cited sentence types.
5. Share the resulting text or screenshot for analysis, omitting any credentials. Test other scenarios only if the first looks correct.

## Non-negotiable boundaries

- No actual Hubitat/MCP or Home Assistant access or device commands. No home history is sent to Ollama in this benchmark. Only static fictional evidence is sent.
- The benchmark directly uses the installed primary Ollama Cloud connection (no new account, token, GitHub secret, failover, or computer).
- Same-origin POST, explicit per-run checkbox consent, at most 4 requests, no retries, no tool schema, a 10-second cooldown and up to 12 attempted Stage 6 cloud calls per hour.
- Errors are category-only, without model raw text, credentials or provider response bodies.
- No automatic runs, periodic jobs, or publication activation. CI invokes mocked model transports only and makes no paid calls.
- Production planner, MCP tool executor, normal HomeBrain answers, heating and fan automations remain unchanged.

**Rollback:** revert the Stage 6 additive PR, reinstall v0.18.294 if necessary.
