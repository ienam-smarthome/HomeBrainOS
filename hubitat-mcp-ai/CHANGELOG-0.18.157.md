# HomeBrainOS v0.18.157 — Schema-compatible read-only controller settings

The 27 October live v0.18.156 Bedroom 3 Mesh test identified the actual
investigation blocker: `controller_config: app_id_missing_from_live_schema`.
An independently recorded command was issued by button app #3103, and the
hub's live tool manifest advertised `hub_get_app_config`, but the V2
pre-planner refused a missing *explicit* `appId` property in the generic
`args` schema.

## Changes

- **Respect the real JSON Schema contract.** For an event-attested command
  issuer, V2 accepts `appId` if the actual live `hub_read_apps_code`
  sub-operation enum contains `hub_get_app_config` AND its nested args schema
  either declares `appId` or is a JSON object with additional properties
  permitted. A closed schema, incompatible type/required argument, missing
  operation, write gateway or unverified issuer is refused. If the generic
  object has an `additionalProperties` schema, the value must satisfy it.
- **No exemption from host safety gates.** The proposed read still passes
  `review_model_read_proposals` with the active full manifest, verified
  evidence IDs, duplicate and budget gates, schema validation, and read-only
  ToolExecutor effect check. No device commands or app writes are introduced.
- **Better field-level diagnostics.** A proposed app configuration read now
  indicates whether its `appId` was explicitly declared or permitted by
  an open, generic args schema. Actual execution and read failures remain
  separately auditable.
- **Inventory timing evidence.** Named-device V2 investigations report bounded
  `inventory_page_diagnostics` in semantic diagnostics: source, mode,
  page count, first/slowest page elapsed time, concurrency and up to ten
  individual page timings. These are client-side MCP elapsed times including
  transport and queue overhead, **not** measured Hubitat CPU runtimes.
- **Regression coverage.** Synthetic tests cover generic open/closed read
  schemas, a typed restrictive additional-properties schema, source-attested
  vs invented issuer IDs, and write/unadvertised-operation denial.

## Outstanding

This addresses an actual live permission-schema incompatibility but does
NOT guarantee the upstream app-config sub-operation will return readable
settings. The next live test must check `bootstrap_diagnostics`,
`read_failures` and `coverage` for an attempted
`hub_get_app_config`. App configuration at read time cannot prove the
effective historical rule conditions at the time of the October 24 command.

The independent 15-second model planner timeout remains a distinct issue;
a 10.9k-character prompt timed out in the preceding test. Identity-only
inventory still took approximately 18.5 seconds and requires page-timing
profiling before changing its freshness/authority contract.

V2 remains explicitly opted-in and read-only. V1 production device controls,
automations and confirmation remain unchanged.

## Live acceptance

1. Re-run Bedroom 3 Mesh read-only investigation. If the live gateway truly
   permits generic `args`, expect `controller_config` to progress from
   `app_id_missing_from_live_schema` to `verified_issuer_proposal` with
   `argument_basis: open_args_schema`, then `read_attempt_completed` or a
   reported read rejection/failure. A stored setting alone is not a cause.
2. Review `semantic_diagnostics.inventory_page_diagnostics` to isolate
   actual slow MCP page offsets.
3. Inspect planning outcome separately; `planning_timeout` is possible and
   is not fixed by this release.
