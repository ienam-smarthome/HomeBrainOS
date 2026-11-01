# Hubitat MCP AI v0.18.342 — HomeBrain vNext model-first pilot

## User-facing change

- Adds `model_first_investigations_enabled`, **disabled by default**. When enabled, an eligible read-only, single-device telemetry investigation prompts Ollama Cloud to explain its collected evidence in natural language, rather than returning source-claim IDs that the server converts into generic sentences.
- The exact first model-authored no-tools draft is retained only if source scope, request-local provenance through coordinator/author/shared completion, reported-status presence, a material uncertainty marker and selected high-risk unverified physical/causal/action claim checks all pass.
- If any gate rejects, the established evidence-first source-rendered answer is used unchanged. Technical JSON records `answerPublicationDecision.mode=model-authored-provisional` on acceptance; otherwise `modelFirstRejection` describes the bounded failure category.
- Ordinary status, lighting, heating, commands, general historical causality, permissions and model access are unchanged. The pre-existing 6-round bounded connectivity read budget, tools, app authorisation and hardware safety are untouched. No additional model or MCP calls are introduced.

## Validation and limits

- Offline tests cover accepted natural prose, unchanged provider-stage identity, missing target/source identity, definite unsupported causes, impossible physical telemetry/command claims and missing caveats. Existing tests exercise default-off compatibility.
- **This is a provisional consistency gate, not semantic entailment certification.** The presence of a health value and caution does not prove every other sentence. Publication will be checked against actual source evidence by a human before any broader rollout.
- Same-question, same-source, first-attempt model-quality improvement remains **NOT MEASURED** pending the opt-in user trace. No claim of Claude parity.
- No home-system writes or configuration changes were made by repository development.

## Manual opt-in test and rollback

1. Update the Home Assistant **Hubitat MCP AI** add-on to v0.18.342.
2. Enable `model_first_investigations_enabled: true` under its configuration and restart the add-on. Leave all other permissions and settings unchanged.
3. Ask a strictly read-only single-device telemetry investigation question once; collect full answer + Technical JSON with the installed version and `answerPublicationDecision`, `modelFirstDraftBoundary`, rounds, tools and elapsed.
4. Disable the setting and restart to restore the established publisher immediately.

The next architectural milestone is one bounded investigation planner and source-complete evidence across multiple domains; this release is explicitly **not** a full pipeline replacement.
