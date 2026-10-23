# HomeBrainOS v0.18.74 — Preserve bounded Rule Machine editor-page observations

## Live finding (23 October 2026)
In a read-only investigation of existing Rule Machine app 4246 and Light Mode Controller app 4019, v0.18.73 correctly retained selected persisted settings values, native health and variable counts, but subsequent `hub_get_app_config(pageName=selectTriggers)` and `selectActions` reads produced API receipts listing only generic response field names. The answer therefore repeated a partial report rather than stating what the editor pages actually displayed.

## Changes
- For successful `hub_read_apps_code / hub_get_app_config` responses scoped to an explicitly requested native editor page (`selectActions` or `selectTriggers`), attach an additional ID-verified, privacy-safe page observation to the **ordinary evidence receipt**, without a second Hubitat request.
- Declassify only a bounded allowlist of recognized action syntax from current page paragraphs: Cancel Delayed Actions, IF/ELSE/END-IF, ON/OFF, and numeric Delay durations with an explicit cancelable marker. Device labels, conditions, arbitrary editor text, passwords, URLs and unrelated settings are never retained in the projection.
- Render recognized **page encounter-order fragments** in the existing-rule partial verdict; describe unparseable pages and truncation explicitly.
- Preserve the completion contract: a current editor page is not an authoritative native compiled action tree or runtime execution. `stored_logic` remains `checked-unverified` without independently validated semantic action-tree evidence.
- Add defensive regression tests for actual action-page patterns, wrong IDs, wrong page, invalid/oversized text, secret redaction and final-answer evidence separation.

## Boundaries
No live Hubitat rules or devices were modified. No automatic creation, disabling or Rule Machine writes were added. This release is a bounded **observability improvement**, not a full Rule Machine 5.1 action-tree compiler. The precise native response schema for app 4246 must be checked in the next live read; a page that does not expose recognizable paragraphs remains unverified.
