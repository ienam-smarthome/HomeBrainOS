# Hubitat MCP AI v0.18.220 — Show verified answer; skip redundant final claim pass

## Actual v0.18.219 live finding (29 October 2026)

The model selected and successfully completed six independent `hub_get_device` reads for source-name-matched Bathroom candidates and a seventh `hub_get_device_attribute` read with an incomplete projection. It correctly recovered:
- Bathroom Light 1 (7818): source-reported `switch=off`, `level=60`, `networkStatus=online`.
- Bathroom Light 2 (7821): source-reported `switch=off`, `level=60`, `networkStatus=online`.
- Bathroom Button (1079): battery 95%, healthStatus online.
- Bathroom Hi-P sensor (7746) and Soft Sensor (7754): inactive motion, networkStatus online.
- Bathroom Meter (7851): temperature 24.2°C and humidity 68%, networkStatus online.

Native V2's **`answer.text` was already correct and complete**, with `concise_answer_source=verified_entity_group_comparison`, `entity_group_summary.verified_device_read_count=6`, `matched_light_count=2`. Yet the *test page* displayed the old nine-fact claim list under “Investigation V2 test” because `test_webui.py` set its main answer text to `data.report?.text||data.answer?.text`. The optional `full_source_backed_answer` in the copyable details exposed the correct answer. This is a **UI selection defect, not failed data collection or reasoning**.

The same run took 20.366 seconds, including an unnecessary final claim-only model pass of **8.008 seconds** before returning `unstructured_withheld`. The model had already collected the entire bounded group in six source-attested reads. One `hub_get_device_attribute` malformed proposal was separately rejected and another returned incomplete attribute metadata. None sent a write.

## Changes

- The V2 test panel now displays `data.answer.text` first and uses `data.report.text` only as fallback when no answer exists. Copy answer and full report retain this same source-grounded presentation. The expanded investigation details **also include `technical_source_report`** separately so no evidence or failed-read audit disappears.
- When a model-selected identity candidate group has completed **all independently ID-matched READs**, the native READ agent marks `final_synthesis_skipped_reason=complete_verified_entity_group` and does not spend another 8 seconds requesting JSON fact selection that cannot add source evidence. Full technical report, witness projections, model read selection and V2 safety gates remain unchanged.
- Incomplete candidate groups are **not** deemed answer-ready. Their subject-relevance blocker and missing evidence remain visible; single-device historical/causal and whole-hub questions retain their previous final-selection pathways.
- New regression tests cover visible answer/report priority, full technical transcript retention, end-to-end six-read group with no final inference call, correct light-state/level meaning, and an incomplete group still using existing validation.

## Limits and next work

This fixes the immediate visible result and a measurable unnecessary inference step. It does not yet provide independent room inventory, source-attested membership of every room device, or general model-authored prose for every question. Those are separate V1 parity goals. No Hubitat devices, rules, automations, controls or production Main Ask routes are changed. Experimental Native V2 remains read-only.
