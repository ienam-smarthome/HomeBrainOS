# Stage 3E — privacy-preserving, local-only investigation trace reporting

Source version: **v0.18.279**. Base: merged v0.18.278.

## What this milestone does

The Stage 3D evaluator can compare provided model-call-shaped traces against
the Stage 3A evidence frontier. However, its input may contain Hubitat device
and app IDs, timestamps, room/device names, model call arguments and other
household details. It is **unsafe to upload or publish raw replay JSON**.

Stage 3E adds a local-only privacy boundary:
`stage3_trace_privacy_report.build_stage3e_private_trace_report(...)`.
It processes the replay *in memory* and returns a **strictly allowlisted,
aggregate-only** result: case/round counts, privacy-thresholded domain totals,
model versus shadow oracle precision/recall, attempted duplicate suppression,
unattested ID suppression and malformed/unsupported read counts.

It does not return raw receipts, tool schemas, messages, arguments, device
or app IDs, event timestamps, source text, user-supplied case identifiers,
per-case rows or any credential material. Domain values are from a fixed
small allowlist; counts in a domain with fewer than 3 cases are rolled into
a suppressed total.

### Local CLI

```bash
cd hubitat-mcp-ai
python tools/stage3e_local_trace_report.py \
  --input /private/path/to/stage3d-replay.json \
  --ack-local-sensitive-processing
```

Input is a locally stored JSON object with exactly one top-level `cases`
array, shaped according to `docs/INVESTIGATION-STAGE-3D-CONTROLLED-REPLAY.md`.
The command reads at most **1 MiB**, does not contact the network or HomeBrain,
does not execute a model, does not call Hubitat/HA, and prints **only the
aggregate JSON to stdout**. It will never print a private input path,
an exception message or the input body on an invalid file. It refuses
to read a file without the explicit acknowledgement flag.

Run this command only on a **trusted local computer** with the required
in-memory or file trace already available. Keep input files private under
the local OS's access permissions. Do **not** paste live Hubitat MCP tokens,
OAuth credentials, personal information or raw trace JSON into a chat or PR.
Only the aggregate JSON may be reviewed after checking it for local policy.

### Source authenticity versus self-labelled input

The current regression cases contain **constructed model-call sequences**,
not authenticated, captured production model calls. `trace_origin` labels
such as `user-labelled-redacted-trace` are user-provided metadata and
cannot prove authenticity. Stage 3E reports zero **independently
authenticated genuine traces** and refuses to declare live improvement or
unlock planner activation—even if the fixture scores are excellent.

Reproducible, genuinely observed production traces require a **separately
reviewed and explicitly enabled local capture workflow**, including a
privacy review, user consent, source integrity checks and a rollback path.
Stage 3E neither provides nor activates a live recorder; the Stage 3C
constructor-based observation remains default OFF.

### Gate and acceptance

The existing original MCP model read-selection and answer publisher are
unchanged. Replays are pure Python calculations with no external calls or
writes. The add-on version increments to satisfy the source-version gate;
**no add-on installation or live update is requested**.

The new regression suite exercises six constructed cross-domain scenarios,
small-cell suppression, output secret/identity exclusion, invalid trace
provenance, malformed/oversized inputs, input immutability, null oracle
semantics, local CLI consent and generic error messages.

Merge only after the **full Python suite**, repository metadata,
HomeBrain validation and add-on smoke checks are green.

**Next decision gate:** once the owner explicitly approves local recording,
design a local, opt-in, privacy-guarded capture facility with independent
provenance and retention controls. Compare genuine read-choice sequences and
answer fidelity before proposing any active Stage 4 model-authored
publication. Avoid installing Stage 3E solely for this offline report.

Rollback: revert this additive PR. No live config or data migration exists.
