# 0.17.89 — Adult household cloud accounts with opt-in, provider-authorised failover

## Defaults
- Existing **single-key and local-first behaviour remains unchanged**. Secondary account routing is OFF.
- Add-on settings: `ollama_household_cloud_failover_enabled=false`, masked `ollama_household_accounts_json="[]"`, `ollama_cloud_first=false`.

## Safeguards
- At most three additional, distinct, consenting adult account credentials; both owner consent **and provider approval for shared use** must be explicitly asserted for each enabled entry.
- No automatic rotation for **HTTP 429**, 401/403, credits, unexpected responses, read/stream timeouts or other ambiguous outcomes. Only pre-send connection failure or HTTP 502/503/504 qualify for cloud account failover. Each eligible account attempted at most once.
- Cloud-first mode can use configured local Ollama as a final fallback for otherwise unresolved failures, including 429; local-first remains the default. No automatic retries of a used API key.
- No key appears in telemetry, chat response, evidence journal or user-visible diagnostics. Only generic per-request failover counters are recorded.

## Provider/account ownership
Ollama's public terms limit use to adults and call for safeguarding credentials. Its shared-usage Team plan is the documented multi-user route. Users must obtain provider permission before authorising cross-person credential use. HomeBrain cannot validate that permission and defaults to deny. Do not pool keys merely to bypass account-level credits or rate limits. A shared household cloud request may contain sensitive information; owners must consent to this explicitly.

## Limitations
No authenticated end-user-to-owner mapping, per-account credit balances, persistent quotas or account selection UI; these remain a later phase. Credentials are managed in Home Assistant add-on password options, not in GitHub or chat. No user/account is automatically enrolled.

## Test gate
Regression: legacy single-key mode, consent-denied accounts, malformed configs, 429 and auth-denial nonrotation, bounded 5xx/cloud connect failover, cloud-first 429 to local and local-first compatibility. Full suite, add-on smoke and repository validation before merge.
