# Hubitat MCP AI 0.16.39

## Preserve causal ordering and exact completed-run durations

The 0.16.38 Hallway live proof correctly kept the focal ON transition, rejected
an older unrelated Maker API command, checked both Hallway dimmers, and exposed
the requested motion/presence timing. It also exposed three presentation details
worth tightening.

### Recorded ordering

When every requested motion/presence event is recorded after the focal device
transition, the deterministic causal summary now says so explicitly.

For the live Hallway case:

- Hallway Light 1 reported ON first;
- Hallway Soft Sensor was recorded about 0.93 s later;
- Hallway FP300 sensor was recorded about 0.95 s later.

Those recorded sensor edges therefore cannot be the Hubitat-side trigger for that
transition. The answer still preserves the important limitation that an upstream
system may have detected motion/presence earlier and delivered state reports to
Hubitat in a different order.

This is an ordering statement about the recorded Hubitat evidence, not a claim
that motion could not have occurred earlier outside Hubitat.

### Exact duration wording

Completed causal runs no longer round a non-exact minute count to phrases such as
`approximately 1 minutes`.

Durations now preserve exact rounded seconds with correct singular/plural units,
for example:

- `1 second`
- `1 minute`
- `1 minute 7 seconds`
- `2 hours 3 minutes 4 seconds`

The underlying interval boundaries are unchanged.

### Aggregate queue-wait metric

The technical timing row `MCP queue wait` is now labelled
`Aggregate MCP queue wait`.

Each semaphore acquisition contributes to this timing, so concurrent work can
make the accumulated queue-wait total differ from wall-clock request duration.
The new label matches the existing `Aggregate MCP HTTP` wording and avoids
implying that the request spent the displayed total in one serial wait.

## Regression coverage

0.16.39 adds tests for:

1. the 67-second Hallway run rendering as `1 minute 7 seconds`;
2. singular one-minute and one-second durations;
3. the recorded-order explanation when all requested sensor reports follow the
   focal transition;
4. suppression of that stronger ordering statement when requested sensor timing
   is mixed;
5. aggregate MCP queue-wait presentation even when it exceeds wall-clock total.
