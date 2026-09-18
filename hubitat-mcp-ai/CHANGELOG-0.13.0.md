# Hubitat MCP AI 0.13.0

## Unified causal finalization

0.13.0 follows the first live validation of the 0.12.0 causal evidence planner.

The 0.12.0 planner successfully acquired the strongest missing provenance evidence:
one exact-room causal plan, one ranked controller history read, and two controller
events aligned with Bedroom 3 Light turn-on transitions. The live evidence showed
physical button-1 events at approximately 00:02:53 and 01:32:51, aligning with the
starts of the two material overnight light-on intervals.

However, the final answer mentioned only the 01:32 transition and omitted the
00:02:53 transition that started the 1h27 interval.

The root cause was architectural: when the model voluntarily returned a no-tool
answer, the orchestrator returned that draft directly. The shared
FinalAnswerCoordinator — including the evidence brief, bounded concrete tool packet,
and validators introduced in 0.11.0 — was therefore not guaranteed to run.

0.13.0 removes that split.

### Every investigative completion uses the shared final coordinator

For analytical/causal history requests, a provider response with no tool calls no
longer returns directly after grounding.

After existing target/capability/device-claim/grounding checks:

- causal completeness is evaluated;
- if no further evidence slot requires a bounded retry, HomeBrain routes the turn
  through the same FinalAnswerCoordinator used by host/budget stop paths;
- the coordinator receives the current-turn evidence brief and bounded concrete tool
  excerpts; and
- causal requests additionally receive the structured causal timeline described
  below.

Routine non-investigative requests keep their existing low-latency direct path.

Metric: `investigative_finalization`.

### Structured causal timeline

The new `causal_timeline.py` joins already-gathered evidence around each observed
subject interval. It does not decide causation.

For every bounded interval it records:

- start/end timestamps and duration;
- controller/button events within 2 seconds of the interval start;
- subject command events within 8 seconds of the interval start/end;
- mode/sunrise/sunset context within 15 seconds of the boundaries; and
- whether the trigger has aligned controller provenance or remains unresolved.

Rows are marked MATERIAL when they are at least five minutes long or carry aligned
controller/command evidence. Short unresolved rows remain visible as minor activity.

The synthesis contract requires every MATERIAL row to be accounted for. Adjacent
short unresolved flickers may be grouped, but a material interval with strong
provenance can no longer disappear from the narrative simply because another
interval is easier for the model to discuss.

### Causal timeline coverage validation

Final synthesis now checks material-row coverage only for causal requests.

The validator does not write the missing explanation. It detects omitted material
start anchors and adds a `causal_timeline_coverage` issue to the existing no-tools
repair pass.

The repair model receives:

- the original evidence brief;
- the full HOST CAUSAL TIMELINE;
- the original draft;
- the missing material row IDs/start times; and
- the existing localized deterministic safety baseline.

This keeps authorship with the model while making omission of strong evidence
repairable and observable.

### One bounded downstream-provenance attempt

The 0.12.0 live subject history also contained boundary-adjacent
`command-setLevel` and `command-off` events. Those prove that commands reached
the device, but they do not identify which app/rule issued them.

When such boundary commands exist and no stronger command-source evidence has been
checked, 0.13.0 gives the tool loop one bounded causal-completeness retry before
final synthesis.

The retry asks for:

- relevant rule/app configuration or execution evidence;
- or native logs;
- using discovery first if the necessary gateway is not already declared.

It explicitly tells the model not to re-read controller history or weaker
environmental sensor history.

A plain `hub_list_apps`/manifest read does not satisfy this provenance slot because
it identifies available automations without showing that a particular one issued
the observed command.

If the bounded attempt cannot obtain stronger provenance, final synthesis must leave
the command source unresolved instead of guessing.

Metric: `causal_completion_retry`.

### Why this is architectural rather than device-specific

No Bedroom 3 device name, app name, rule name, or timestamp is embedded in runtime
logic.

The new layer operates on general evidence shapes:

- a temporal subject history;
- one or more event-style controller histories;
- command events near interval boundaries;
- location/mode history; and
- app/rule/log evidence classes.

The same pipeline applies to another light, switch, fan, valve, lock, or other device
with compatible history evidence.

## Regression coverage

0.13.0 adds tests for:

- joining two controller-provenance events to two material subject intervals;
- keeping short unexplained flickers visible but non-material;
- preserving boundary commands and nearby mode context in the causal timeline;
- detecting the exact live-answer failure shape where 01:32 is mentioned but the
  material 00:02 interval is omitted;
- accepting an answer that accounts for both material start anchors;
- requesting one downstream provenance attempt when command source is unresolved;
- ensuring a list-apps manifest does not falsely satisfy command provenance;
- suppressing the retry after native log evidence is checked; and
- repairing an incomplete final synthesis through the shared coordinator while
  preserving model authorship.

## Live acceptance target

Repeating "Why was Bedroom 3 Light on during the night?" should now produce a final
reasoning pass that, when supported by the same hub evidence:

- accounts for the 00:02:53 physical button-1 alignment and the 1h27 interval;
- accounts for the 01:32:51 physical button-1 alignment and the later 12m interval;
- groups the brief pre-midnight unexplained flickers rather than silently assigning
  them the same cause;
- distinguishes the physical/button provenance from later set-level/off commands;
- makes one bounded attempt to identify the app/rule/log source of those downstream
  commands; and
- leaves any still-unresolved automation source explicit rather than guessed.
