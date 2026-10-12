# HomeBrain 0.17.33 — Require archived sensor evidence in focal answers

## Live regression

HomeBrain 0.17.32 completed the Bedroom 1 Light OFF investigation at 17:14:04.380 BST in **10.5 seconds**, one model round and 17 tool calls. It correctly performed two bounded MCP sensor reads with verified time limits (both returned **zero** rows), and the journal receipt independently retained **four** collector-received FP300 and Soft Sensor observations. Version 0.17.32 put those observations in the focal causal evidence graph, but the model was free to omit them in the written answer; its negative-claim guard only activated for an assertion that all sensor history was empty.

## Fix

- Include the local Historical Journal as a separately labelled, typed source in the **highest-priority pre-synthesis causal answer plan**: retained observation count, per-sensor values, timestamp basis, two verified MCP windows with zero returned events, non-exhaustive coverage and provenance limits.
- Require final synthesis to compare archived observations and native bounded history rather than summarizing them as unqualified nearby inactivity.
- Add a **source-backed completeness guard** for the case where the generated answer does not mention the archive or omits its timestamp-quality limitations. It adds one concise, factual Historical Journal paragraph near the evidence assessment; it never identifies an OFF actor or claims a five-second timer ran.
- Avoid duplicating an answer that already identifies the Historical Journal with the collector-reception caveat. Do not add archived facts when no archival observations were retrieved.
- Treat the evidence-backed localized archive repairs as eligible for the existing **one-model-round** completion path, rather than unnecessarily invoking another AI turn.
- Regression tests reproduce the 0.17.32 answer omission, verify answer-plan obligations, preserve separate MCP and journal counts, and check no duplicate or invented disclosures.

## Safety and scope

Read-only. No new Hubitat requests, device/rule mutations, changed journal capture schedule, retention settings or database migration. Your existing seven-day and 200,000-row configuration remains in place. Timestamp order in the archive reflects collector reception unless original source timestamps are available; close reception to OFF is **not** proof of causality.

## Live test

Upgrade HomeBrain to 0.17.33 and repeat the **same** Bedroom 1 Light investigation. The answer should explicitly include **4 Historical Journal motion observations** and **2 verified MCP sensor windows returning 0 rows**, with collector-received timestamps distinguished from original device times. The OFF cause should remain unresolved without actual command/execution evidence. Check runtime, model rounds and technical trace for one-pass completion.
