# Hubitat MCP AI 0.16.97

## Nightly one-time Rule Machine cleanup

- HomeBrain now runs a dedicated cleanup scheduler at **01:00 Hubitat local time** by default.
- Cleanup is deliberately narrow: only Rule Machine entries whose names exactly match HomeBrain's `(One-time YYYY-MM-DD HH:MM)` convention are eligible.
- A one-time rule is eligible only after its embedded scheduled time has passed by the configured safety grace period (10 minutes by default).
- Future one-time rules, recurring rules, ordinary Rule Machine rules, and malformed look-alike names are never submitted for deletion.
- Each eligible rule is removed through MCP `hub_delete_native_app` using **soft delete only** (`force=false`, `confirm=true`), preserving the MCP server's backup/safety checks.
- If the rule-list read fails, cleanup deletes nothing. If one individual delete fails, cleanup records the failure and continues with the remaining eligible rules.
- The scheduler uses the same authoritative Hubitat-local timezone resolver as one-time authoring, so the 01:00 run follows GMT/BST and other DST transitions without a fixed offset.
- Destructive cleanup has no startup catch-up run: if HomeBrain is restarted after 01:00, expired rules wait for the next scheduled 01:00 pass rather than being deleted unexpectedly during startup.

## One-time rule lifecycle

- Newly authored one-time schedules no longer add `Pause Rules: **This Rule**` after their device action.
- The lifecycle is now: create -> execute once -> remain inert -> nightly cleanup removes the expired generated rule.
- Existing one-time rules created by older HomeBrain versions remain eligible for the same nightly cleanup once expired.
- Regression coverage verifies the prompt-to-confirmation path queues exactly one Rule Machine create write for a one-time request and no `pauseRule` follow-up.

## Configuration

- `one_time_rule_cleanup_enabled` defaults to `true`.
- `one_time_rule_cleanup_time` defaults to `01:00`.
- `one_time_rule_cleanup_grace_minutes` defaults to `10`.
