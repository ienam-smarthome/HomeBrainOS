# HomeBrainOS v0.18.299 — Stage 6.4: split cloud decisions from evidence-completeness reviews

## Actual observed result

The user's real Stage 6 run showed:

- `Check cloud connection`: **HTTP 200** from Ollama's account-status endpoint, so the primary API key was accepted for that endpoint, **not** guaranteed for every chat request.
- `Stage 6 adaptive evidence selection failed: invalid structured model response` during the first planning round. That message combined invalid JSON, absent fields, contradictory plans and malformed value-of-information review, so its exact cause is **not recoverable** from the screenshot.
- Since main had moved to v0.18.298, it was necessary to account for the stricter live `homebrain-stage6-next.v2` planner contract requiring every unread source's optional explanatory appraisal alongside READ/STOP control.

## Principled contract separation

A fictional multi-step investigation has two independently evaluated surfaces:

1. **Bounded machine-action control**, which must always pass: exact JSON object, recognised plan schema, action strictly READ/STOP, source ID from the **actually offered unread list** (or null on STOP), 1–240-character rationale, and no unauthorised control keys. The model never receives hidden reference relevance labels, a real MCP tool or home context.
2. **Investigation completeness appraisal**, which measures whether the model considered every unread source against unresolved questions. If the optional v2 questions or source appraisals are malformed or incomplete, the model's already-valid READ/STOP decision may proceed as **explicitly degraded/unaudited**. The actual missing or malformed ledger is recorded under bounded, static issue identifiers. The response **does not** claim the appraisal was complete, and host-held gold relevance is still scored independently.

An explicit STOP contradicting **any present valid self-assessment** that identifies an unread useful source is *still rejected*. Unknown or repeated selected source IDs, invalid actions, wrong schemas, non-JSON text, unbounded rationales and extra JSON keys are rejected. No free-form prose is parsed for tool decisions and no guessed source is used.

## Observability and limits

- Errors now report a **safe static category** such as `not_one_json_object`, `missing_decision_fields`, `invalid_or_unknown_source_choice`, `self_contradictory_stop` or `incorrect_plan_schema`, never the original model output, token, provider body or private logs.
- For a recovered, safe action with incomplete appraisal, the dashboard displays **Planning contract: incomplete or unaudited**, per-step audit issues, and the actual withheld-reference source recall. No false claim of certified natural-language reasoning is made.
- This is **not** a syntax-repair or model-retry mechanism. It neither invents a model answer nor automatically schedules additional provider calls. It preserves the same maximum three synthetic reads and four cloud attempts per explicitly consented run.
- An incomplete STOP can still be a bad investigation: its missing sources and expected finding types remain visible. The complete model-authored prose is still not verified, and `publisher_approval` remains false.

## User test after update

1. Upgrade Hubitat MCP AI to **v0.18.299**.
2. Under Stage 6, retain **Delayed OFF report versus device time**, tick consent for **up to four cloud requests** and run once.
3. If the first model response is not valid JSON or has invalid control fields, share only the displayed safe error category. Do not repeatedly retry.
4. If a result appears, check `Planning contract`, `Unanswered questions and per-source value assessments`, selected source IDs, and exact source-value atoms. A complete result should ideally select S1, S2 and S3 and distinguish event-source times from collector receipt times; an incomplete source ledger does not count as successful completeness.

## Boundaries

No real household context, Hubitat or Home Assistant reads/writes, control, source journaling or automation modifications; all evidence is synthetic. Production publisher, routing, models and MCP executor remain unchanged. Cloud use is only on explicit manual user consent through the installed web UI, using the user's existing primary Ollama Cloud account. GitHub CI tests rely only on mock cloud clients and make no billable requests.

Prior versions and all Stage 4–6 synthetic benchmark tests remain available. This release corrects the evaluation protocol; it does not establish that Gemma reaches Claude-equivalent investigative ability.
