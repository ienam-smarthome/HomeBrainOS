# Hubitat MCP AI v0.18.368 — source-complete native parent and one-time rule inventory

## Real user-facing failure (2026-11-02)

Installed v0.18.367 successfully cleared the unsupported checkpoint metric crash, but its first-shot read-only Rule Machine inventory question returned an unrelated generic existing-rule verification refusal. The evidence packet records six successful nonmutating Hubitat reads (two complete instances requests, native rules, filtered instances, app source and system app types) with no typed retained parent or exact one-time rule matches. The final answer had neither the asked native parent ID nor the requested existing one-time-rule names/IDs, and invented an irrelevant "comparison controller" evidence obligation. **9 model rounds, 6 MCP calls, 44.626s wall, 42.049s agent, 39.928s Ollama provider**; status was unresolved. This is a documented failed first-shot response, not a benchmark over multiple cases.

## Cause

The generic existing-rule verifier requires a source-checked *complete executable action tree*. The user instead asked for **which native Rule Machine parent app exists and which existing rules match a name pattern**. Generic gateway receipts expose only response field names ("apps, count", "rules, count"); the answer calibrator discards the model answer if no action tree is present, including when the actual question is about *inventory* and has no focal action tree. Tool reads were spent searching source code ID 18 and duplicate app listings rather than retaining typed app/type/parent and rules-list facts.

## Fix

- For standalone, read-only, factual Rule Machine inventory questions without an individually targeted app ID or historical causal objective, make three host-owned **READ-only** Hubitat MCP calls: installed app instances, app types, native rule inventory. No native management or create tool is exposed to the model.
- Join a candidate Rule Machine instance with a built-in app type only via **matching appTypeId** and the returned app type's **namespace=hubitat / name=Rule Machine**. Never guess parent ID from matching child counts or names. Treat incomplete app-type/instance pages as a limitation, and display the ID as unverified if the join fails.
- Identify dated one-time rules only with a complete literal suffix "(One-time YYYY-MM-DD HH:MM)"; preserve source-matched IDs and parentId links where returned. Check row counts/cursors/truncation before claiming absence. Disagreeing source names are excluded, not papered over.
- Preserve separate evidence obligations: a rule inventory can be complete without providing a full native action tree. This path answers the actual lookup concisely, without the deep-rule-only generic report, repeated provider rounds or unnecessary Groovy source requests.
- If a dated one-time rule exists and its mixed native management gateway is installed, the host may make **one explicitly validated operation=read** native document call for the first matching ID. Report stored trigger/action methods only when its typed document is complete. This never creates, deletes, pauses or executes any rule.
- New synthetic regression covers app-type source join, false matches, pagination, no-match uncertainty, matching names and IDs, preservation of read-only effect, and no-model first response. The separate existing-rule deep-verification and native-write safety contracts remain unchanged.

## Verification, limitations and rollback

Expected improvement for the fixed question: a first-pass factual answer with fewer unnecessary provider turns, backed by a typed inventory receipt, and no write/confirmation. **Actual installed v0.18.368 answer, user-visible latency and current parent/one-time IDs are NOT MEASURED.** Synthetic fixture rows are not current Hubitat observations. A missing one-time rule in a bounded page cannot establish global absence. Any native document read establishes stored configuration, not runtime execution.

Revert the source/route commits to restore the v0.18.367 model-first path. Do not re-enable creation based on inventory alone: the offline one-time compiler still requires a verified dated one-time native document, parent type and modern create schema, plus the existing write safeguards.
