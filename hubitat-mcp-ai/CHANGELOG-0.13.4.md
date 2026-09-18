# Hubitat MCP AI 0.13.4

## Window-scoped evidence and known-history fast path

0.13.4 follows the first live validation of 0.13.3.

The 0.13.3 causal fence behaved correctly:

- outcome remained Success;
- `causal_subject_empty_stop=1`;
- model rounds stayed at 2;
- no controller/location/app/rule causal expansion occurred;
- total latency fell to 11.4 seconds; and
- the previous 00:02/01:32 causal story was no longer resurrected from prior
  conversation history.

That run exposed two narrower issues.

### Window-scoped evidence survives zero intervals

The final answer correctly stated that no bounded on interval was established, but
also referred to overnight `setLevel` / `off` commands.

Those command rows may exist in the full current-turn device-event page even when
the deterministic state-pair analysis yields zero bounded intervals. Because the
technical evidence receipt only retained the newest ordinary rows, the final claim
could be grounded during synthesis yet difficult to audit afterward.

0.13.4 adds `window_event_evidence()`.

For any semantic history window it:

- filters the full fetched source page to rows whose timestamps actually fall inside
  the requested start/end bounds;
- keeps command, state, level, and custom event rows without inferring causation;
- orders the bounded result chronologically; and
- stores the rows separately as `windowEvents`.

This selection is independent of:

- the newest-first `observedEvents` cap;
- whether the caller explicitly specified a state attribute;
- whether deterministic interval construction found any active interval.

`DeviceHistoryService` derives `windowEvents` from the full unfiltered source
page, so typed history such as `attribute=switch` does not lose nearby command
rows. Post-fetch enrichment backfills the same evidence channel when an older or
alternate path did not already supply it.

The evidence receipt keeps up to 24 bounded window rows. When no observed interval
exists, the current-turn evidence ledger renders up to 10 of those rows so final
synthesis can distinguish "commands were recorded in the requested window" from
"an active interval was established."

### Positive source attribution is validated

The live 0.13.3 answer said "the logs show..." even though no native
`hub_get_logs` evidence source had been checked.

A new positive source-attribution guard now detects that narrow mismatch.

When:

- the draft positively attributes a fact to "logs";
- no current-turn log source was successfully checked; and
- current-turn device-event history exists,

the localized validator changes only the source label to "recorded device-event
rows" and sends the issue through the existing model repair pass.

If native logs were actually checked, the wording is left unchanged.

### Generic investigations skip unnecessary upfront discovery

History/causal reasoning already has a stable local evidence registry containing:

- target resolution;
- deterministic device history;
- room filtering;
- location history; and
- the later purpose-specific causal provenance phase.

For generic investigative history prompts that do **not** explicitly request
logs/apps/rules/automation, 0.13.4 therefore skips the original-request fuzzy
`hub_search_tools` call.

Explicit provenance-source requests still use normal discovery.

Metric:

- `history_known_tool_fastpath`

### App manifest is now demand-driven

Generic history investigations no longer preload `hub_list_apps` into the system
prompt solely because they are investigative.

The app manifest is still included when the current or previous user request
explicitly mentions apps, rules, or automation.

For implicit causal questions, rule/app/log evidence is activated later only after
the current subject history establishes a transition worth investigating.

This removes unrelated upfront hub work from empty-subject requests while keeping
the bounded causal-completion path introduced in 0.13.1/0.13.2.

## Regression coverage

0.13.4 adds tests for:

- filtering full source rows to the requested semantic window;
- retaining command rows when deterministic interval count is zero;
- serializing `windowEvents` independently of the latest-event cap;
- rendering zero-interval window evidence in the current-turn ledger;
- repairing "logs show..." when only device-event history was checked;
- preserving that wording when native logs were actually checked;
- classification of generic vs explicit-provenance investigative requests;
- generic causal history system-prompt construction not preloading the app
  manifest; and
- end-to-end generic causal history avoiding the initial `hub_search_tools` and
  app-manifest calls.

## Live acceptance target

Repeat the same Bedroom 3 causal question while the current history page still
contains no bounded overnight on interval.

Expected:

- `causal_subject_empty_stop=1`;
- `history_known_tool_fastpath=1`;
- `tool_discovery_calls=0`;
- no `hub_list_apps` evidence receipt;
- no controller/location causal expansion;
- any overnight command rows referenced by the final answer are visible in
  `details.windowEvents`;
- the answer calls them recorded device-event rows unless native logs were actually
  checked; and
- total latency should remain around or below the 0.13.3 11.4-second result, subject
  to provider/Hubitat variance.
