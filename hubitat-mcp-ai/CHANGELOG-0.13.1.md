# Hubitat MCP AI 0.13.1

## Bounded causal completion and boundary evidence retention

0.13.1 is a focused follow-up to the first live 0.13.0 causal validation.

The 0.13.0 answer quality was materially better: the final synthesis accounted for
both material Bedroom 3 Light intervals, preserved the short pre-midnight activity
as unexplained, and separated physical controller provenance from later turn-off
commands.

The live run also exposed two remaining architectural costs:

- the investigation still reached 8 model rounds and 16 tool calls;
- after the correct controller had already been proven, the model reopened generic
  device exploration, including a missing auxiliary controller lookup, which marked
  the entire otherwise-useful answer as unresolved.

The same run also showed that newer daytime events can push earlier boundary command
rows out of the ordinary bounded `observedEvents` evidence list.

0.13.1 addresses those issues without changing the causal interpretation layer.

### Preserve boundary-near rows independently of newest-first truncation

`history_temporal_analysis.boundary_event_evidence()` selects source events that fall
within eight seconds of any deterministic observed interval start/end.

The selection is performed from the full fetched source page before the normal
newest-first presentation cap is applied. The bounded rows are stored separately as
`boundaryEvents` with their nearest boundary delta.

This means an investigated overnight `command-off`, `command-setLevel`, state, or
level row remains visible even after later activity fills the ordinary latest-event
window.

`causal_timeline.py` now prefers `boundaryEvents` and supplements them with
`observedEvents`, de-duplicating by timestamp/name/value.

`evidence_ledger.py` uses the same preserved rows for its compact boundary-event
hints.

### Enter causal completion immediately when the evidence graph says to

After the host exact-room causal plan has already found controller provenance, the
orchestrator now checks for unresolved boundary command-source evidence immediately.

If boundary commands are present, it starts the existing causal-completion phase in
the same round instead of giving the model another unrestricted investigative round.

This removes a live source of redundant reads such as:

- resolving a generic version of an already-proven controller;
- re-reading unrelated controller/device history;
- reopening location/device exploration merely because budget remains.

### Restrict causal completion to provenance reads

During causal completion, the model receives a reduced tool view containing only:

- `hub_search_tools`;
- read-only `hub_read_*` gateways whose live name/description/schema exposes
  app, rule, log, or diagnostic evidence.

The phase deliberately excludes:

- local device-history tools;
- location-event tools;
- generic target/device resolution;
- device inventory reads; and
- mutating Rule Machine gateways.

If discovery is required, one search round may expose the relevant read gateway.
After the first non-search provenance read attempt, HomeBrain proceeds directly to
the shared final synthesis path.

If the model emits a hidden/disallowed tool call despite the reduced schema, the host
does not execute it; the call is returned as a bounded provenance-phase error and
HomeBrain finalizes from the evidence already gathered.

### Outcome behavior

No global outcome-policy exception is added.

Instead, auxiliary device resolution is structurally unavailable during the
completion phase, so a missing speculative controller cannot increment
`device_resolution_missing` and downgrade an otherwise answered causal
investigation to `unresolved`.

Primary target resolution remains unchanged: a genuinely missing or ambiguous device
still yields the existing unresolved outcome.

## Regression coverage

0.13.1 adds tests that verify:

- a boundary command remains selected when 18 newer daytime rows precede it;
- the ordinary latest-16 evidence list can omit that command while
  `boundaryEvents` still preserves it;
- the causal timeline consumes preserved boundary commands;
- causal completion exposes search/read app-rule-log gateways;
- device/history/location tools are excluded;
- mutating rule-management gateways are excluded.

## Live acceptance target

Repeating the same Bedroom 3 causal question should retain the useful 0.13.0 answer
shape while reducing fan-out.

In particular:

- both physical button alignments should remain in final synthesis;
- the 01:30 / 01:45 boundary command evidence should remain available even when
  later daytime events exist;
- no generic Bedroom 3 dimmer or Ikea controller lookup should occur after aligned
  provenance is established;
- the completion phase should search/read only app/rule/log provenance;
- a failed auxiliary provenance read should remain an evidence gap rather than a
  missing-device outcome;
- total model rounds/tool calls should be lower than the 0.13.0 live run.
