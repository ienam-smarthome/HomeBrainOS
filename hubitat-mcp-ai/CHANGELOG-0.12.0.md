# Hubitat MCP AI 0.12.0

## Causal evidence planning

0.12.0 follows the first live validation of the 0.11.0 investigate → evidence brief
→ synthesize architecture.

0.11.0 fixed the answer-authoring boundary, but the live Bedroom 3 run exposed a
different weakness in evidence acquisition:

- the model chose `homebrain_filter_devices(room contains "Bedroom 3")`;
- controller evidence hints were only emitted for exact-equality room filters;
- the host therefore never performed the ranked dimmer/button provenance read;
- the model fell back to weaker motion checks;
- a sparse room-context target cache allowed `Bedroom 3 Sensor T1` to be reused
  without attribute metadata, so the history capability guard could not prove that
  `motion` was unsupported;
- final synthesis saw the subject intervals but did not see several command events
  already present in the subject history near transition boundaries.

The result reasoned more than 0.10.x, but still missed the strongest evidence path.

### Host-owned causal evidence planner

For why/cause/trigger requests, subject history now establishes structured subject
metadata first.

The planner then:

1. derives the exact room from the resolved subject;
2. performs one exact-room device discovery independently of model filter syntax;
3. ranks same-room button-capable controllers from advertised capabilities;
4. reads exactly one highest-ranked controller using its strongest suggested event
   attribute such as `pushed`, `held`, `released`, or `doubleTapped`;
5. compares controller event timestamps with observed subject active-transition
   starts; and
6. surfaces alignments within two seconds as high-value provenance evidence.

The planner selects evidence. It does not write the causal answer.

A close controller alignment is stronger provenance evidence than motion or
illuminance correlation, but it still does not identify the person who operated the
control unless upstream event metadata explicitly supplies that provenance.

### Evidence-priority continuation

When an aligned controller event exists, the model is told not to spend the
remaining investigative budget on weaker environmental histories merely to explain
the already-aligned transition.

Remaining reads should instead test:

- downstream rule/app configuration or execution;
- native logs;
- schedules/mode behavior; or
- subject transitions that remain unexplained.

If no controller candidate or no temporal alignment exists, the model can continue
to the next strongest evidence class.

### Room filter semantics no longer hide controller hints

Room filtering with either `eq` or `contains` now exposes controller source hints
when the matching room/context set contains button-capable devices.

The causal planner itself uses exact room metadata, so correctness no longer depends
on the provider choosing the same filter operator as a regression test.

### Metadata-aware request-local target cache

Typed history reads for known attributes now make request-cache reuse depend on
what the sparse target can actually establish.

A structural room/context scan may seed a target containing only identity, room, and
capabilities. That sparse record remains sufficient when it positively advertises
the requested capability—for example `MotionSensor` authorizes a `motion` history
read with no extra device lookup.

When the sparse record does **not** positively advertise the required capability and
also lacks current attribute metadata:

- request-local resolution deliberately misses the cache;
- a detailed targeted device lookup refreshes the target;
- the requested history attribute is checked against the detailed advertised
  attributes/capabilities; and
- provably unsupported history is rejected before event-history execution.

This preserves the low-latency Soft Sensor path while closing the 0.11.0 path that
allowed an illuminance/temperature sensor to be queried as a motion sensor after
room discovery.

Metric: `resolution_cache_metadata_miss`.

### Boundary-adjacent subject commands survive synthesis

Temporal history evidence previously emphasized intervals while event-style
controller histories preserved concrete rows.

0.12.0 also includes bounded subject command/state rows that occur within eight
seconds of observed interval starts/ends in the final evidence brief.

This preserves evidence such as:

- `command-setLevel`;
- `command-off`;
- switch/level transitions immediately around a boundary.

Those rows help the reasoning model distinguish:

- the event that likely initiated the light state;
- downstream automation that adjusted level;
- the command that switched it off; and
- timing correlation that remains non-causal.

### Conservative zero-history wording

Serializer-side zero-history protection now also catches generic wording such as
"No motion was recorded" when the underlying history stream is explicitly
unverified.

Such claims are rewritten to the established bounded form: no active interval was
established from the recorded rows, but that does not prove the device stayed
inactive throughout the requested window.

### Metrics

0.12.0 adds:

- `causal_room_plan`
- `causal_provenance_read`
- `causal_provenance_aligned`
- `resolution_cache_metadata_miss`

These make live-soak evidence acquisition visible without logging private
reasoning.

## Live acceptance target

For the Bedroom 3 investigation, a successful run should:

- automatically inspect the ranked Bedroom 3 button/dimmer controller after the
  subject history;
- preserve any aligned `pushed` event around 00:02:53 and 01:32:51 if the hub
  actually reports those rows;
- stop treating the Bedroom 3 illuminance sensor as a motion sensor;
- use remaining evidence budget to inspect relevant automation/rule/log behavior
  instead of weaker room-sensor fan-out;
- preserve boundary-adjacent light commands such as level/off commands in final
  synthesis;
- distinguish the likely turn-on provenance from subsequent automation effects; and
- retain the unverified-event-stream caveat without allowing it to erase the causal
  explanation.
