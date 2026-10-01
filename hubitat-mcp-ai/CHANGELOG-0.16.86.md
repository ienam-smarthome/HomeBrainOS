# Hubitat MCP AI 0.16.86

## Performance evidence intelligence

This release keeps the accepted broad-performance architecture unchanged and fixes two evidence-intelligence defects exposed by the 0.16.85 live proof.

### Hubitat long-call WARN parsing

Hubitat execution-time warnings commonly format millisecond durations with thousands separators, for example `166,621ms` or `401,699ms`. The adaptive diagnostic classifier previously accepted only unformatted digits, so genuine multi-minute `runQ` warnings could be misclassified as neutral observations.

0.16.86 accepts both comma-formatted and plain integer millisecond values, normalizes them to integers, and classifies qualifying long calls as `diagnostic_signal` evidence. This allows the final answer to report the observed long-call signal while retaining the existing boundary that the exact implementation defect, worker-thread blocking, and user-visible impact are not proven without stronger evidence.

### Adaptive target ranking

The one-device/one-app adaptive expansion remains bounded, but app/device eligibility no longer has an all-or-nothing 20% `pctBusy` cliff. A 15% busy-share value may enter the retrieval ranking, while 20% remains the stronger priority bonus. This prevents a sustained near-threshold busy-share leader from being discarded solely because a live snapshot is slightly below 20%, while an isolated high `averageMs` row can still qualify and compete by score.

The thresholds remain retrieval-policy inputs only; they are not user-facing health or severity classifications.

### Architecture unchanged

- Quiet broad-performance request: 3 host reads, 0 exploratory agent rounds, 1 synthesis round.
- Adaptive request: maximum 5 host reads, 0 exploratory agent rounds, 1 synthesis round.
- At most one device-scoped and one app-scoped diagnostic read.
- No extra provider round, no broader diagnostic fan-out, and no duplicate performance snapshot replay.

### Regression coverage

The release gate covers:

- comma-formatted `runQ` durations from the 0.16.85 Nest live proof;
- backward compatibility with plain integer millisecond durations;
- preservation of a real long-call diagnostic signal through the format-independent presentation guard;
- an 18.8% busy-share app outranking an isolated ~3-second-average app for the single adaptive app slot;
- quiet rows remaining below adaptive expansion; and
- the one-device/one-app adaptive cap remaining intact.
