# HomeBrainOS v0.16.136 — scheduler-key candidate attribution and direct optimisation routing

## Changes
- Scheduled-job analysis now retains dictionary/map keys when decoding `scheduledJobs` records. This prevents losing the only job identifier when returned entries are keyed objects instead of ordinary lists.
- Narrowly decode `devNNNOnce` and `appNNNOnce` identifiers appearing in a job ID, job key, or schedule-map key. These become **unverified owner candidates**, never authoritative owners without an explicit app/device identity check. Show candidate type, numeric ID, method, and queued entry count separately from verified-owner totals.
- Handle an unrelated or numeric job-row `id` alongside an encoded map key without losing the candidate mapping. Do not infer owner identity from display names or partial/prefix matches.
- Plain requests such as "Analyse all scheduled jobs, group by owner and handler, identify unnecessary work and recommend efficiency improvements" now trigger the host-collected performance/scheduler evidence workflow, rather than the generic model-directed tool loop.
- Include host-derived scheduled-job grouping in these scheduler-only optimisation reports as well as whole-hub reviews.
- Fix the live v0.16.135 LG TV diagnostic contradiction: the `Hypothesis 2: LG webOS TV Latency` heading now provides the required target context to correctly report that a scoped 6-hour log read succeeded but returned no rows, rather than claiming no diagnostic read took place.
- Regression tests cover list and map job shapes, strict key patterns, verified vs candidate ownership, route selection, and diagnostic source attribution.

## Safety and limitations
- No Hubitat automations, schedules, drivers or devices have been changed.
- Scheduler key naming is not an authoritative owner assignment. Candidate IDs must be checked against current device/app identity and any relevant dependencies before editing schedules.
- Matching next-run timestamps do not establish simultaneous execution, CPU spikes, or predicted savings. Complete scheduler code/dependency graphs remain issue #733.
