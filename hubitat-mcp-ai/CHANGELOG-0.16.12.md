# Hubitat MCP AI 0.16.12

## Deterministic native-log boundary correlation

0.16.11 recovered the missing Dehumidifier 2 switch interval and correctly
queried the native-log window around the turn-on boundary. Live evidence then
showed a stronger provenance pattern that HomeBrain was not yet exploiting:

```
22:07:36.926  Ikea Rodret button 2 pushed [physical]
22:07:37.002  Dehumidifier 2 turn on command
22:07:37.107  Dehumidifier 2 switch=on
22:07:37.159  Humidity Controller manual-run reaction
```

The previous causal pipeline still treated the physical button as only an
unproven coincidence because it did not automatically inspect and correlate the
matching turn-off boundary.

0.16.12 makes native execution logs the first causal provenance layer after a
subject interval is established.

## Both boundaries are queried host-side

For each recent material interval, HomeBrain derives native-log windows from the
observed state boundaries themselves.

For the live Dehumidifier 2 interval:

```
start = 2026-09-22T22:07:37.107+0100
end   = 2026-09-22T22:38:13.489+0100
```

the host derives:

```
START logs: 2026-09-22T21:07:27.107Z .. 21:07:47.107Z
END logs:   2026-09-22T21:38:03.489Z .. 21:38:23.489Z
```

These reads are host-generated and run in parallel when MCP concurrency permits.
No model is asked to invent or convert the timestamps.

## Structured provenance chain

Native log rows are parsed into structured source records:

- device/controller/app type;
- source ID;
- source label;
- local log timestamp;
- payload.

For each subject boundary HomeBrain deterministically searches for:

1. the matching subject device command close to the state boundary;
2. a physical controller/input event immediately before that command;
3. downstream app reactions immediately after the command.

The resulting correlation keeps separate timing deltas for:

- physical controller -> subject command;
- subject command -> state boundary;
- physical controller -> state boundary;
- subject command -> downstream app reaction.

## Repeated start/end corroboration

A single nearby physical button event remains strong timing evidence but is not
enough for early causal finalization.

HomeBrain only takes the new fast provenance path when the same physical
controller/input fingerprint is observed immediately before both:

- the subject ON command at the interval start; and
- the subject OFF command at the interval end.

For the Dehumidifier 2 golden case, the expected repeated fingerprint is the
same Ikea Rodret device ID plus button number 2.

This repeated mirrored sequence is treated as strong temporal provenance. Final
synthesis must present that controller/input as the strongest initiating-control
candidate, while retaining the explicit caveat that repeated timestamp
correlation does not independently prove the configured button-to-device
mapping or identify a person.

## Downstream automation is kept separate from initiation

If app log rows occur after the subject command, they are classified as
downstream handling.

For the golden case, the Humidity Controller's manual-run lock and 90-minute
timer messages occur after the Dehumidifier 2 ON command. HomeBrain therefore
describes the app as reacting to/managing the already-started manual run, not as
the initiating source.

## Evidence-quality short circuit

When repeated start/end native-log provenance is established, HomeBrain now
skips weaker causal fan-out:

- room inventory correlation;
- same-room controller history;
- motion/presence correlation;
- location/mode history;
- app manifest/config navigation.

It proceeds directly to final synthesis from the stronger native execution
evidence.

If native-log evidence is missing or insufficient, all existing 0.16.11 fallback
evidence paths remain available.

## Metrics

Adds:

- `causal_native_log_reads`
- `causal_native_log_correlations`
- `causal_repeated_controller_pattern`

A successful repeated-boundary Dehumidifier investigation should normally show
two native-log reads, two correlated boundaries and one repeated-controller
pattern.

## Expected live answer shape

The causal conclusion should be calibrated along these lines:

> The strongest initiating-control candidate is Ikea Rodret button 2. It was
> physically pressed immediately before the Dehumidifier 2 ON command, and the
> same controller/button was again pressed immediately before the later OFF
> command. The Humidity Controller logged its manual-run handling only after the
> ON command, so it reacted to the manual start rather than initiating it.
> Repeated timing strongly supports the association, although the logs alone do
> not independently prove the configured button-to-device mapping.
