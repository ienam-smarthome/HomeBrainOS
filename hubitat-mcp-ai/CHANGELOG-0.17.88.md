# HomeBrain 0.17.88 — Ollama Cloud 429 handling

## Live incident
A request to investigate a selected unexpected device state change returned `Client error '429 Too Many Requests' for url 'https://ollama.com/api/chat'`. MCP was online and 36 tools were advertised. The failure was in the cloud model request, not evidence of a Hubitat hub or MCP outage. No investigation conclusion can be assessed from this failed request.

## Improvement
- Preserve upstream Ollama Cloud **HTTP 429** instead of misclassifying it as a generic HomeBrain HTTP 502. The user sees a safe, actionable explanation of capacity, concurrency and usage-credit possibilities; a 429 alone does not uniquely distinguish them.
- If Ollama supplies an integer Retry-After between 1 and 3600 seconds, forward and explain it. Do not invent reset times or reflect arbitrary provider body/headers.
- Do **not** retry provider HTTP status errors automatically, preserving the transport's existing behaviour. Additional retries can worsen a limit and increase API usage.
- The browser now checks the API response status and does not append failed assistant exchanges to conversation history. MCP status and model-provider availability remain conceptually separate.
- The pre-existing local-first Ollama configuration is unchanged. If a reachable local model is configured, it is attempted first; the cloud fallback is still only attempted if that local path fails.

## Scope
No Hubitat settings, device controls, rules, MCP permissions, model billing settings or cloud credit balances were modified. The change doesn't create local models or bypass provider limits.

## Validation
Regression tests for 429 safety, non-429 discrimination, bounded Retry-After values, API behaviour and browser failed-history handling. Full GitHub CI and manual Home Assistant update required before considering the add-on deployed.
