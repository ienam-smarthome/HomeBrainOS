# Hubitat MCP AI v0.18.219 — General entity-aware answers

## Paired V1/V2 result (29 October 2026)

The production Main Ask (V1) replied in **19.984 seconds** using **two read-only MCP calls**, `hub_list_devices(labelFilter="Bathroom",detailed=true)` and `hub_get_room(room="Bathroom")`. It identified eight name matches, reported Bathroom Light 1 and 2 OFF with stored level 60% each, described room assignments for six matched devices, and added the Shower Light from the verified room inventory. Its diagnostic `outcome=unresolved` was driven by missing causal device/command history even though the request was about current state and room membership; future general outcome evaluation should not require causal coverage for a noncausal question. The user-visible V1 text was substantially more useful than V2.

Native V2 v0.18.218 ran in **16.812 seconds**, with six model-chosen, identity-matched `hub_get_device` reads (all six successful) and no writes or timeouts. Source evidence attested **Bathroom Light 1 (7818) switch=off, level=60** and **Bathroom Light 2 (7821) switch=off, level=60**, two motion sensors inactive, button battery 95%, and meter temperature 24.2°C and humidity 68%. Despite recovering all this, its model final claim selection was nonstructured. The generic fallback published the **first nine of fifteen individual attribute facts**, omitting Bathroom Light 2 entirely. It had neither a room inventory nor projected room fields, so V2 could not verify room assignments or discover the non-name-matched Shower Light. V2's raw duration was ~3.2 seconds shorter, but answer completeness and directness were worse.

## Architectural correction

- Introduce `native_entity_group_answer.py`, a **generic, bounded entity-aware answer composer** that consumes *only* model-selected live identity candidate groups and independently verified `hub_get_device` receipts with exactly matching scoped request/returned IDs. No room, app, device-name or question-specific routing is added.
- For a complete group of at most eight candidates, produce a direct answer with **every individually read device**, its source label, source-advertised Light capability (not inferred from a name), meaningful allowlisted state attributes and exact read references.
- State `switch=off` separately from `last reported level=60%`. A previously stored level is not evidence of emitted light while switched OFF. No name match establishes actual room membership or completeness of the room inventory; the answer explicitly discloses those limits.
- **Do not** publish a falsely complete group when any expected candidate lacks an independently scoped device receipt or the returned ID mismatches. Such cases retain the earlier source-relevance blocker. Unrelated broad investigations and detailed causal reports retain existing answer paths.
- Expose `entity_group_summary` and `concise_answer_source=verified_entity_group_comparison` diagnostics for paired V1/V2 tests. Preserve the entire strict claim audit and source trace in the full technical report.
- Add regression tests using the six-device 29 October evidence structure, completely different area labels, incomplete/mismatched source IDs, fabricated telemetry and a full model-selected READ-agent replay reproducing rejected JSON claim selection without losing the second light.

## Remaining limitations / next development

This is a host-verified, readable fallback; the model still needs a broader and more useful validated natural-language synthesis interface. Native V2 can compare the name-matched device group, but it does not yet independently inspect a complete room inventory, report verified room membership or identify named-in-room devices absent from the name match. The next architectural step should enable typed room relationships and independent read-source completeness rather than guessing from labels. The model should choose that read when room membership is material.

No device controls, writes, automations or production Main Ask operations were modified. V2 remains experimental and READ-only. Better-than-V1 status remains **unverified** until identical live tasks produce comparable answer quality and speed.
