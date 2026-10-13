# HomeBrain 0.17.44 — Source-linked focal event selection and configuration authority

## Motivation: three independent live investigations (13 October 2026)

- A question asking for the **latest manual OFF** selected the 13 October
  08:43:44 light OFF, even though no physical controller input or hub OFF
  command proved it was manual. The same 24-hour source history contained an
  **earlier verified physical button 1 press at 23:49:27.303 BST on 12 October**,
  app 1251 OFF command at 23:49:27.336, and light OFF at 23:49:27.529.
- A separate app-4019 configuration query established that the persisted
  `motionOffLockoutMinutes` value was **300**, while the question described
  the *expected* duration as three minutes. Expectation and configuration
  were previously conflated in some answers.
- A model-issued log search for **23:49 BST** mistakenly used 23:49 UTC,
  missing the event by one hour. Generic investigation sometimes made
  broad whole-hub reads and four model rounds, despite targeted sources.

## Cross-source investigation architecture

New `focal_event_provenance.py` separates these distinct evidence classes:

1. **Latest observed OFF**: light-state transition, regardless of cause.
2. **Latest verified manual OFF**: a time-linked, native physical button event,
   matching numbered button-controller app OFF command and light state within
   a conservative bounded interval. Where there is no such chain, the
   manual nature remains unverified, even if the app producer label mentions
   a button. A newer unrelated OFF does not displace a proven manual event
   when manual provenance is the user's stated objective.
3. **Explicit date/time anchor**: historic wall-clock times can only be
   converted using an offset grounded in a native event on the requested
   date; the absolute MCP query windows remain UTC. An ungrounded
   historical offset is an unresolved query, never silently reinterpreted
   as current UTC or another day's offset.
4. **Current persisted configuration**: directly read
   `hub_get_app_config(includeSettings=True)` once and extract only the
   configured duration/mode fields, separate from rendered UI summaries
   and the user's expectation. That source does not prove the same value
   was configured when a historical event occurred. Typed duration
   comparisons show expected, configured-now, and log-reported values
   independently; they do not invent actual lockout suppression.

The existing historical lockout prefetch uses the shared selector, looks up
the configured controller with **at most one extra targeted native
device-history read**, and then reuses existing bounded app-log and
Historical Journal paths for the selected event. It does not conduct a new
whole-hub scan, issue device commands or change any automation settings.

## Evidence safety and limitations

A physical push, hub command and light OFF form strong corroborating
evidence for a manual OFF, but do not prove app 4019 evaluated or enforced
its lockout. Missing controller history and absent command rows remain
unknown, not a negative conclusion. A settings read from today does not
establish what the app was configured to do yesterday. Motion eligibility
and effective suppression remain separate verification questions.

This release focuses on **manual-event selection, current settings authority
and historical UTC anchoring**. Broader cross-room causal discovery and
general model-round budgets remain future work, rather than claims of
improvement not supported by this implementation.

## Regression tests

Tests cover the real physical button1→app1251→light7805 sequence, the newer
unverified OFF, numbered-button mismatches, no button history, explicit
BST-to-UTC conversion, refusal of unsupported date/time offsets,
persisted 300-minute settings versus a three-minute request, and an
end-to-end read-only prefetch ensuring app logs query the **selected manual
event**, not the unrelated later state.

## Safety and validation

Read-only; no Hubitat app/device writes, scheduled changes, journal schema or
7-day/200,000-row retention changes. Live verification still required after CI.

Update to 0.17.44 and repeat the **exact same** read-only question for
latest *manual* OFF of Livingroom Light 1. The technical output should
separately identify latest observed OFF on 13 Oct and selected verified
manual OFF on 12 Oct, preserve the actual button 1 and app1251 evidence,
and distinguish the persisted 300-minute setting from requested three
minutes. Verify additional hub reads remain targeted and bounded.
