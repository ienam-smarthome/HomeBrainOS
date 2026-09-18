# Hubitat MCP AI 0.11.0

## Evidence-first reasoning synthesis

0.11.0 is an architectural change to historical/causal reasoning rather than
another device-specific live-soak patch.

The release was driven by side-by-side validation against a stronger tool-using
assistant. HomeBrain 0.10.470 successfully gathered much of the same raw evidence
for the Bedroom 3 investigation — subject light history, mode history, room
context, and a `pushed` history read for the top-ranked dimmer/controller — but
the API answer still collapsed to a duration-only sentence.

The failure was therefore no longer primarily evidence acquisition. It was the
boundary between investigation, synthesis, and deterministic correction.

### Two evidence budgets

Everyday reads retain the established bounded profile:

- 3 model tool rounds
- 8 model-directed reads

Analytical history requests (why/cause, comparison/correlation, normality) now use
a request-local investigative profile:

- 5 model tool rounds
- 12 model-directed reads

The wider profile exists to connect heterogeneous evidence classes, not to sweep a
room or hub exhaustively. Writes and confirmation flows remain outside the read
budget.

### Causal and analytical modes are separate

Cause/trigger questions are now distinguished from comparison/normality requests.

Causal mode asks the model to build an evidence-strength timeline:

1. subject event history;
2. direct controller/provenance or native log evidence;
3. relevant rule/app configuration or execution evidence;
4. mode/location context;
5. weaker environmental correlation only when materially useful.

Comparison/normality questions receive the larger analytical budget without being
forced through controller-specific causal behavior.

### Automation identity is available to investigations

Investigative requests now receive the live app manifest for identity/navigation
even if the user never says "app", "rule", or "automation". The manifest is not
treated as proof of configuration or execution; it lets the model identify and
target relevant rule/app reads instead of guessing names.

### Controller provenance is one evidence source, not the stopping point

For causal requests, room discovery may still provide one deterministic
highest-ranked button/controller history read. This prevents the two live-observed
failure modes:

- skipping controller evidence entirely; and
- fanning out across every button device.

Unlike 0.10.470, that host-owned read no longer forces immediate synthesis. The
model can spend remaining investigative budget on a different evidence class such
as rule/app configuration or logs when the user's causal question requires it.

### Event-style histories are first-class evidence

Evidence receipts previously retained rich details only when history produced
binary `temporalAnalysis`. Button/remote histories such as `pushed`, `held`,
or `released` therefore degraded to generic "object fields" summaries.

0.11.0 keeps up to 16 bounded event rows with:

- event name/value;
- timestamp;
- description;
- unit/state-change metadata when present.

This preserves direct controller provenance such as physical/button descriptions
for final reasoning without pretending those events are binary state intervals.

### Dedicated final evidence brief

Final synthesis is now a separate no-tools reasoning phase.

HomeBrain appends:

- a structured current-turn evidence brief describing checked source classes,
  observed subject intervals, controller events, close mode correlations, and
  reliability; and
- bounded excerpts of the actual privacy-redacted tool-result payloads, including
  recent rule/app/log results when those sources were read.

These are appended at the end of final context so normal conversation/tool
compaction cannot hide the strongest evidence.

The synthesis contract explicitly preserves the user's original objective. For
causal questions it asks for:

- the best-supported explanation and calibrated confidence;
- a chronological multi-source timeline;
- separation of trigger/provenance from downstream automation effects;
- remaining unexplained transitions/evidence gaps; and
- configuration suggestions only when supported and relevant.

### Deterministic guards are validators, not answer authors

The previous architecture allowed a duration-safety guard to replace an entire
investigative answer with a deterministic duration sentence. In the 0.10.470 live
run this erased useful controller/mode evidence from the response even though it
remained present in the evidence array.

0.11.0 changes that boundary:

- duration correction treats line breaks as claim boundaries, so Markdown
  bullets/tables do not become one giant replaceable "sentence";
- the duration guard no longer falls back to replacing the entire synthesis when
  it cannot isolate a claim;
- whole-answer zero/unverified history fallback is limited to genuinely
  single-source simple history requests;
- multi-source synthesis is checked by a validator;
- when a deterministic conflict is detected, the model receives one no-tools
  repair pass with the original draft, evidence context, issue labels, and a
  localized factual correction baseline;
- only if the repaired draft still violates an invariant does HomeBrain fall back
  to the localized deterministic correction.

### Context and budget isolation

The reasoning profile is request-local. Ordinary resets return to the standard
budget, while the transport's first-turn counter reset explicitly preserves the
profile selected for the active request.

The obsolete 0.10.467–0.10.469 controller-reservation budget state and its tests
have been removed. There is now one request-level evidence-budget policy.

## Regression coverage

0.11.0 adds coverage for:

- event-style button histories retaining timestamped descriptions;
- controller event rows appearing in the final evidence brief beside subject
  intervals;
- investigative 5/12 vs standard 3/8 budget profiles;
- duration correction preserving supported causal analysis on later lines;
- bounded current-turn tool evidence packets preserving controller and diagnostic
  results while excluding discovery noise;
- deterministic top-ranked controller selection without lower-ranked expansion.

## Expected live acceptance behavior

For the Bedroom 3 question, HomeBrain should no longer answer with only
"1h44m across five intervals".

A successful 0.11.0 run should use the gathered evidence to explain the strongest
supported trigger/provenance relationship, place it on the same timeline as the
light transitions and relevant mode/rule behavior, distinguish automation effects
from the original turn-on cause, call out any remaining unexplained activity, and
retain the unverified-event-stream caveat without allowing that caveat to dominate
the answer.
