# v0.18.331 — Answer Quality Q1: developer tools off the main dashboard

## Why
The normal HomeBrain dashboard showed four large, separately collapsed experimental sections above System Check: Ollama Cloud benchmark, Stage 5 independent AI investigation, Stage 6 conflicting evidence, and Live Shadow preflight. The active Answer Quality roadmap now measures **real sourced HomeBrain answers**, not synthetic experiment pass rates, so these panels distract from ordinary use.

## Change
- One new closed **Advanced testing & diagnostics** section collects the existing options.
- The three older cloud/synthetic experiments are nested in their own closed **Legacy cloud experiments** section. They remain available for engineering comparisons, and their previously required cloud-account consent checkboxes are preserved.
- Live Shadow and all separate read-only consent gates, historical journal, Command Shadow and app-log follow-up remain accessible under the same advanced section.
- System Check, its scheduled status, manual run and Pushover report remain directly visible after the advanced section.
- No benchmark API endpoint, app capability, tool request, authentication, Cloud routing, causal publisher, automation, device command or configuration is changed.
- Add a web-UI structure/consent regression suite to verify all old IDs, cloud consent, live-read consent and health controls persist.

## Important limitation: live answer quality not fixed by UI cleanup
A Q1 v0.18.330 diagnostic exposed a **reporter-to-initiator attribution error**: the model treated a bridge-produced state report typed `physical` as high-confidence evidence that the bridge or physical interaction initiated a light-OFF action, despite source evidence consistent with an approximately 15-second motion-inactivity mechanism and incomplete command history. This failure is recorded as an **unscored diagnostic** in `docs/ANSWER-QUALITY-Q1-LIVE-OBSERVATIONS.md`. The new UI does not resolve it or claim any measured improvement.

## Acceptance
- Dashboard: advanced section initially collapsed; expanding gives optional historical tools unchanged; System Check immediately visible.
- Existing cloud and live consent checks still guard every operation.
- All repository and Home Assistant add-on tests, CI and smoke tests green prior to merge.
- The next milestone remains a frozen read-only HomeBrain Q&A, a source-reviewed first-attempt baseline and model-independent correction evaluated across unrelated cases.

## Rollback
Restore v0.18.330 if the nested mobile layout interferes with accessibility; no backend or stored state migration is involved.
