# HomeBrainOS v0.18.424 — native proposal answer-quality publication guard

## Observed regression (5 November 2026 at 21:02 UTC)

An installed 0.18.423 read-only review of the upstream MCP Rule Server 5.1.6 dated-trigger runbook returned invented native field formats (`atTime#` as `HH:mm`, `atDate#` as `MM/dd/yyyy`), an invalid `addTrigger`/`addAction` create payload with top-level `parent_id` and invented `runCommand` log action, and asserted the design was READY while coverage reported `evidenceComplete=false`. Only two app inventory and two guide reads were recorded. The model described current app/device page findings without performing targeted reads. The shared rule-design guard appended a hard-coded 23:00–06:00 motion/light caveat from a different rule-design scenario.

No Hubitat change was executed and no confirmation was queued, but the output was unsafe to copy into an authoring workflow.

## Correction

This is a **general source-publication contract improvement**, not a new dated-rule scheduler or exact incident case workaround.

- In the shared `rule_design_claim_guard`, when a request lacks independently source-attested combined native schema evidence, replace asserted upstream-tested field contracts and affirmative READY assessments with an explicit unverified/NOT READY determination.
- Remove executable-looking `operation=create/update/delete/form` native JSON from unverified rule-design proposals. Mere guide availability is not native field attestation.
- Compare actual recorded targeted `hub_get_device` / `hub_get_app_config` reads with model claims; generic app inventory and guide acknowledgments do not certify labels, current config, hub time zone or native write schemas.
- Append overnight motion/light/lockout cautions **only when the actual request** concerns that domain. Other native design reviews receive a generic safety/verification appendix.
- Keep the existing trusted typed combined-schema opt-out and preserve correct motion-rule safety coverage. Add regression tests replaying the 21:02 response and its unsupported JSON with source-only receipts.

## Evidence and boundaries

Independent upstream date type tests from MCP Server PR #576 accept `atDate#` as `type=date`, `yyyy-MM-dd`, and the source runbook includes a full native `atTime#` time representation. This release **does not** claim that the installed hub's dated one-shot rule action and firing have been verified.

No Hubitat calls, native writer authorisation, model round, backup, editor form, rule, device, router, or app change is introduced by this patch. GitHub CI is not live acceptance; rerun the same read-only contract review after installing 0.18.424. Any future creation requires a separately verified actual schema, fresh backup and explicit user approval.

## Evaluation

Expected: no false READY or runnable JSON, no unrelated 23:00–06:00 appendix, source claims correspond to executed receipts, no extra MCP reads. Measured installed accuracy and latency are pending. Continue the permanent benchmark-first Answer Quality roadmap.
