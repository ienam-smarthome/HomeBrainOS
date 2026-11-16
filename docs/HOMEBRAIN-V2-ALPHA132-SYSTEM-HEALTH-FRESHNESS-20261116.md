# HomeBrainOS V2 alpha.132 — System Health activity age and runtime snapshot

**Status:** merged [PR #1700](https://github.com/ienam-smarthome/HomeBrainOS/pull/1700) at `4284b84c8568cb48f7b2bb0aec07080b900a846a` after **4/4 exact-head CI workflows green**. Installed source-real acceptance remains outstanding.

## Scope and existing implementation

The V2 System Health tab already includes named lighting, motion, contact,
water, active-heating, battery, offline and other ON-switch summaries and
troubleshooting shortcuts. Reimplementing it would duplicate existing
read-only, non-model work. This release adds two missing data views.

1. **No recorded activity in over 24h:** based exclusively on each
   returned inventory device's explicit, timezone-aware `lastActivity`
   timestamp. A single existing `hub_list_devices` snapshot is the
   source; no event-history or per-device calls are made. An activity gap
   is **not** an offline, broken, missing-telemetry or fault confirmation.
   Battery-powered/sleepy devices may be quiet by design. Unknown,
   malformed, timezone-less and future timestamps are excluded from both
   the count and the timestamp-coverage denominator. The list is bounded
   and displays each member's hours since recorded activity. Exactly 24h
   is not over 24h.
2. **HomeBrainOS runtime:** reuse the already-retrieved page-start
   `/api/status` response for three separate cards: application
   configuration (configured does not mean connected), recorder status and
   last saved probe time (never a live connectivity test), and optional
   Hub & Device Monitor configuration (no connection/history test).
   Opening System Health, expanding names or switching tabs performs
   **zero extra** source or LLM requests.

The existing device overview remains a single explicitly user-refreshed
read-only snapshot, and the recorder's existing independent collection
schedule is unchanged. No V1, heating scheduler, AI routing, approval,
native write, background poll or additional hub scan is introduced.

## Verification

Fictional deterministic tests exercise active/inactive timestamp bounds,
timezone awareness, missing/future values, exact 24h boundary, source
coverage, capped member lists, and exactly one native inventory query.
The Node UI regression checks the new card, cached runtime rendering and
non-LLM tab/navigation behaviour. Require all exact-head CI workflows
green before merge.

A new alpha.132 device-inventory read on the installed add-on is the
acceptance test for the real names/coverage. Confirm that devices with
old `lastActivity` are labelled **quiet** rather than offline; verify
runtime cards do not trigger another status/device/model request. No
causal first-answer quality benefit is claimed from this feature.
