# v0.18.236 — complete-interval evidence contract

## Live regression reproduced

The V2 request to investigate the most recent **complete** heating ON/OFF
cycle returned a battery level and one scheduled Thermostat OFF command after
32.916 seconds, with nine attempted reads, one 20-second unbounded device
inventory timeout, and repeated Rule Machine/custom-rule mismatches. The
10 returned thermostat events started at 15:15 and ended with an unrelated
22:30 mode OFF event, not a verified heating-start/heating-stop pair.

## General-purpose architectural changes

- A **source-attested interval coverage contract** checks for paired
  operating start/end state events in the source-scoped event history.
  A setpoint command, schedule OFF action, mode setting, battery reading,
  or current snapshot alone can never represent a completed operating
  interval. The source is explicitly bounded and not claimed physically
  independently verified.
- The investigator exposes the interval evidence to the AI immediately
  after a scoped event read; the model itself chooses any follow-up.
  If it prematurely finishes with missing start/end evidence, one bounded
  completion challenge asks it to seek an independently scoped historical
  read or acknowledge the gap.
- No validated pair means **do not** label the investigation complete
  merely because multiple tool types and catalog facts were read.
  A natural-language insufficient-evidence explanation supersedes the
  irrelevant command-count/battery fallback, with complete diagnostics.
- A verified start/end pair from a *relative-time* question is now eligible
  for the existing strict source-cited model reasoning protocol. No
  fabricated calendar date or assumption about the upstream decision.
- A uniquely resolved device never needs an unbounded `hub_list_devices`
  merely to inspect its own events, even when the user asks for the
  *most recent* interval instead of specifying a date.
- Source-verified Rule Machine (`Rule-5.1`) definitions cannot be read
  through the incompatible custom-rule engine. Two actual failures of
  an operation suppress an unproductive third attempt; other supported
  operations and identities remain available.
- A bounded source-verified acronym label family, such as the multiple
  installed TRVs, can be resolved as an **unverified candidate group**
  for model-selected individual reads, not an assumed shared room or
  promoted root-cause target.

## Safety / limits

All operations remain model-selected and independently read-only-guarded.
No writes, inferred missing physical states, forged device IDs or
source-completeness claims. An actual comparison of scheduler decision
records with contemporaneous TRV states still requires both to exist and
be retrieved live. Passing synthetic tests is not a live quality measure.
