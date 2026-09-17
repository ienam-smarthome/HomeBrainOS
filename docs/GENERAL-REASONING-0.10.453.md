# General evidence reasoning in 0.10.453

HomeBrainOS keeps deterministic code authoritative for facts, target resolution, arithmetic, time windows, units, privacy, confirmation, and write verification. The model is responsible for understanding the user's complete objective, choosing among already-declared tools, deciding whether the gathered evidence is sufficient, and explaining the result.

The 0.10.453 loop is intentionally question-agnostic:

1. The model reads the complete request and may emit one or several native tool calls.
2. HomeBrain executes the declared calls through `ToolExecutor` and records authoritative evidence exactly as before.
3. If the model emitted several calls in one round, legacy deterministic presenters are prevented from ending the request after the first presentable result. The complete round executes first.
4. Provider-bound tool results carry the same generic evidence-review contract: re-read the original request, check every material part, fetch more evidence only when it is materially missing, synthesize rather than dump fields, and distinguish observations/calculations from inference.
5. Once evidence is sufficient, the model writes a concise answer. If the tool-round ceiling is reached, `FinalAnswerCoordinator` applies the same evidence discipline with further tool calls disabled.

Single-tool questions retain the existing deterministic presenter fast path, so a simple request such as “which lights are on?” does not gain an unnecessary extra model round. Direct deterministic reads and routine-control paths in `homebrain_agent.py` are unchanged.

Reasoning-capable Ollama model families receive native `think=true`. The transport discards provider `thinking` fields before messages enter the HomeBrain transcript. Hidden reasoning is therefore used only inside the provider to improve tool selection and synthesis; it is not returned, persisted, or exposed through evidence.

This release deliberately adds no question-specific regex or phrase parser. New failures should be evaluated as reasoning/evidence capabilities rather than patched with another wording-specific route unless the operation itself requires a deterministic safety contract.
