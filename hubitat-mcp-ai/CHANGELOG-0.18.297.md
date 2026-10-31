# HomeBrainOS v0.18.297 — Stage 6.2: Cloud connection diagnostics

## User-observed failure

After the successful v0.18.296 Stage 6.1 merge, the actual user attempted the fictional "Delayed OFF report versus device time" investigation and received:

"Stage 6 adaptive evidence selection failed: credentials/permissions. No retry was attempted."

This was a failed **first provider request** (before selecting sources), not a source-understanding failure. The old error wrapper combined HTTP 401 and HTTP 403, hiding an essential diagnostic distinction. The "Ready" badge only checked that a primary cloud key and model were present; it never tested provider acceptance.

Earlier Stage 4–6 calls succeeded using the same configured cloud model. Therefore, do not assume a permanent invalid key or advise immediate replacement without determining the exact status.

## Implemented

- A manually initiated **Check cloud connection (no AI request)** button in the Stage 6 dashboard.
- Calls the documented official `https://ollama.com/api/balance` endpoint via a server-side HTTPS GET, using the existing primary key. Never sends a prompt, requests model tokens, accesses Hubitat/MCP, writes devices, or reveals the account's balance or response JSON.
- Exposes **only** HTTP status or a sanitized network category and a short explanation. Non-inference doesn't imply zero account API rate limits.
- HTTP 200 means the account endpoint accepted the key but does **not** guarantee the chat model is permitted, reachable or not rate limited.
- HTTP 401 means account credentials rejected; HTTP 403 is access denied and **does not by itself prove an invalid key**. HTTP 402 indicates billing/plan action; HTTP 429 rate limiting. Unknown codes, connection errors and provider faults are distinct.
- Stage 6 model-request errors now distinguish 401 vs 403 and suggest the new diagnostic. No automatic retries, account rotation or provider body disclosure.
- The existing configured status now explicitly says **Configured (not yet authenticated)**.
- The diagnostic is manually triggered only, requires same-origin JSON + custom header, one in flight, 10-second cooldown and at most six account checks per process hour.
- Mock-only CI tests verify all status categories, no key/credit leaks, no chat calls, no retry, origin checks and unchanged publisher/device paths.

## Test from your phone

After upgrading Hubitat MCP AI to v0.18.297, expand **Stage 6 · Conflicting evidence**. First tap **Check cloud connection (no AI request)** without ticking the synthetic benchmark consent checkbox. Share only the resulting HTTP status and category. Do **not** retry the four-call Stage 6 cloud benchmark until the status is understood.

If account check succeeds but Stage 6 still returns a 403, the account endpoint is accessible but the model-chat endpoint was denied. This calls for checking Ollama's account policy, permissions, rate/security restrictions, or provider outage without asserting a specific cause from the status alone.

Do not paste API keys, raw provider responses, account balance or household credentials into chat or GitHub.

## Limitations

This checks account API credential acceptance, **not full model/chat access**. No live direct call, user secrets or production Hubitat/HA state can be tested by GitHub CI. The installed add-on must be upgraded by its operator; the code merge does not change running software.

All other reasoning, publisher, tool routing, source-evidence semantics, devices and automations are unchanged.

Rollback: revert this PR and restore v0.18.296.
