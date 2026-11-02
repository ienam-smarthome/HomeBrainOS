# Hubitat MCP AI v0.18.365 — native Rule Machine document reads are not writes

## User-reported live evidence

The installed 0.18.364 read-only native Rule Machine investigation needed a first round of sensitive-action confirmation, even though the requested native sub-operation was `hub_set_rule(operation="read")`. The successful read later returned a native document in 3.793 seconds, but its evidence receipt was incorrectly labelled `effect=sensitive_write` / `mutates=true`, and the response was `request_class=write`. A read must not be recorded as a successful device/rule mutation. The earlier first response spent 24.032 seconds, with 3 provider rounds, two read tools and one queued confirmation; its later 3.793s answer cannot be counted as an independent first-shot benchmark.

## Change

- Classify **only the validated native document `read` envelope** as `ToolEffect.READ` on the installed native rules/app management gateway (and compatible rule-machine gateway): exact `hub_set_rule` selector, positive integer `rule_id`, `operation="read"`, optional boolean `confirm`, and restricted read-only paging/section arguments.
- A boolean `confirm=true` is not write proof: upstream `toolSetRule` runs the `read` branch independently of `confirm`. Reject malformed read lookalikes; `create`, `update`, `form`, unknown properties, ambiguous field values, and native form mutation remain confirmation-protected or blocked by read-only user authority.
- Add synthetic effect-level and model/host orchestration regressions checking no extra confirmation, no write receipt, honest read request class, and negative cases. No native authoring compiler is enabled.

## Native authoring limitations

The user's independently returned native Rule Machine document confirms an existing **daily** 22:00 time trigger and switch OFF action, with typed settings and a successful structured read. That establishes a useful native field exemplar; the child-to-parent ID is not directly returned and no future calendar-date one-time trigger or self-disable-after-execution semantics has been proven. **Native create remains unsupported.** Do not reuse a past confirmation or submit a new rule until the remaining source and safety prerequisites are established.

## Measurement and rollback

Regression pass and CI are required. Real post-install first-attempt usefulness and paired latency are **NOT MEASURED**. No live Hubitat or HA changes during development. Roll back this release through the repository PR if any unrecognised native operation is admitted.
