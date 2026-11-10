# HomeBrainOS v2 — live first-answer review (alpha.29)

## Causal-path discrimination checklist (10 November 2026)

A credible command issuer and an exact event timestamp may be fully supported even when **why the issuer acted** is unknown. For a causal first answer, the reviewer must compare all materially configured explanations that could create the focal action, not just the closest timestamp. When multiple timers or mechanisms align, mark the internal trigger **plausible but unverified** unless event-specific callback/decision evidence, comprehensive participating inputs or another discriminating source establishes a unique path. Distinguish current settings from those demonstrably active at the event time, and preserve original timezone and sub-second event order. Treat a tool call that returned data as distinct from complete historical coverage; record missing sensor/actor sources, window limits and any actual tool errors. A schema-recovery feature is **not tested** by a case containing zero schema failures.


**Default (10 November 2026):** Ordinary Ask/Chat replaces compulsory blind A/B scoring as the main development feedback loop. The original experimental pages remain available under **Experiments (optional)**. This is not independently blinded accuracy measurement.

## Daily workflow

1. Confirm the installed v2 add-on version in the header and ask any everyday question in **Ask / Chat**. For investigation-only testing say **Do not change anything**. Ordinary Ask uses the configured MCP permissions and is not forced read-only by this UX change.
2. Inspect the answer. When review is helpful, click **Copy for review**, or **Technical details / Tool receipts → Download PRIVATE JSON**. The packet includes the captured question, original answer, executed read/command receipts, errors and timing. The copy action runs locally in the browser, with **no automatic external upload**. Check sensitive household content before pasting.
3. Review 0/1/2 scoring for factual grounding, source completeness, causal calibration and usefulness; n/a only if genuinely inapplicable. Check actual records, source windows, chronological order, tool failures, event producer versus command initiator and reporting versus physical device outcome. No receipt is independent truth verification; missing records do not prove absence of an event.
4. Record supported claims, unsupported definite causes, unknowns, missed discriminating reads, tool-schema failures and a single **general** improvement. The reviewer can return **unverified** rather than assigning false certainty. Keep evidence files private and record only privacy-safe failure patterns in the repository.
5. Cluster failures across new day-to-day questions. Implement small general mechanisms with fictional regression tests and evaluate using fresh questions. Do not tune only to exposed historical incidents or advertise a population-level accuracy rate based on informal ChatGPT-assisted reviews.
6. Improve everyday status and control, lighting, heating/TRVs, ventilation/humidity, energy metering, automations, mobile/TV UX and external diagnostics independently from formal A/B work.

## UI roadmap

- Now: Ask and Hub Diagnostics visible first, collapsed optional labs, shorter question area, one-click private review packet.
- Next: clearer answer/activity status, helpful event timestamps and receipts navigation, mobile/TV layout and graph readability.
- Later: opt-in private summary of recurring failure categories, with no automatic score generation or cloud sharing.

## Safety and release gate

No changes here to the production native MCP Agent, model prompts, command contract, token permissions, approvals, Rule Machine, router, Home Assistant or the external recorder. Existing technical export and studies remain intact. The ordinary Ask endpoint can still perform permitted writes; remote model calls can incur costs. Verify UI/backend/config alpha.29 alignment, desktop/mobile navigation, clipboard failure path, unchanged original technical export, CI and container smoke before release. A merged PR does not prove the add-on is installed.
