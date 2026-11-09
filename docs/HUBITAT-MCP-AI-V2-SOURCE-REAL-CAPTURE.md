# HomeBrainOS v2 — Frozen source-real first-answer capture (offline)

**Date:** 9 November 2026. **Status:** prepared and offline-verifiable; genuine hub captures have **not** yet been collected or judged.

This next milestone is distinct from the already-unblinded six fictional `hold-..` cases. It freezes ten new, cross-domain questions with private user-selected device/app labels, then validates **first-attempt Technical JSON** from the existing v2 Ask interface. The capture checker makes **no** MCP, Home Assistant, model or network calls and cannot turn anything on/off. Source-real accuracy remains **not measured** until an operator runs the new questions against a real connected server and a reviewer checks the receipts.

## Check the actual Read / Write permissions (before further live tests)

The source-real `sr-01` Technical JSON reported top-level `readEnabled: true` and `writeEnabled: true`. **These are global MCP Rule Server Read / Write master settings**, not proof that the HomeBrain v2 client token has write permissions. The upstream server's `hub_get_info` adds a **`clientAccess`** object *only when authenticated with a recognised per-client access token*, including that token's `readEnabled`, `writeEnabled` and visible tools.

On the **Hubitat hub itself**: **Apps → MCP Rule Server → Settings → Advanced → Per-client access tokens** (requires firmware 2.5.2+). Select/create a dedicated `HomeBrain v2 Read-only Evaluation` client. Set **Read ON / Write OFF** for that client, and ensure its local/cloud endpoint permissions suit your connection. Keep the global master Write ON if other MCP integrations still need it. Copy **only that client's endpoint/token** privately into the HomeBrainOS v2 add-on's MCP connection settings; **never** paste tokens into a chat, Technical JSON, README, or GitHub.

Use a fresh `hub_get_info` read *through that HomeBrain v2 connection*, and inspect the result for **`clientAccess.writeEnabled: false`** and **`clientAccess.readEnabled: true`**. Seeing only top-level `writeEnabled: true` does **not** prove the token is writable; seeing a token's own `clientAccess.writeEnabled: false` is read-only permission **reported by the server**, still not independent proof of enforcement. Do not run any write command merely to test a permission boundary.

The offline `source_real_acceptance.py verify` report now includes a privacy-safe `permission_evidence` section derived from successful `hub_get_info` receipts, clearly separating `global_write_enabled_reported` from `per_client_write_enabled_reported` and excluding any names/tokens/URLs. For older captures made with the main token, per-client grant fields remain `null`. `read_only_permission_independently_verified` deliberately remains `false` because receipts cannot independently prove enforcement.

Upstream documentation:
[Per-client access tokens](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/README.md) and
[hub_get_info field contract](https://github.com/kingpanther13/Hubitat-local-MCP-server/blob/98bc7ca2d0f1bd2e2857962292b33d83683bc2b0/TOOL_GUIDE.md).

## Private setup

Use a **new private folder outside the public repository** for all configuration, questions, outputs and exported receipts. Create a local `labels.json` like this, replacing the six uppercase placeholder values with exact names from the actual hub (never commit or publish it):

```json
{
  "labels": {
    "light": "YOUR_LIGHT_LABEL",
    "temperature_sensor": "YOUR_TEMPERATURE_SENSOR_LABEL",
    "trv": "YOUR_TRV_LABEL",
    "automation": "YOUR_AUTOMATION_NAME",
    "metered_plug": "YOUR_METERED_PLUG_LABEL",
    "contact_sensor": "YOUR_CONTACT_SENSOR_LABEL"
  }
}
```

From the repository root (Windows / PowerShell):

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py init --config "C:\\Private\\HomeBrain-Acceptance\\labels.json" --directory "C:\\Private\\HomeBrain-Acceptance\\study"
```

This **one-time** command creates a sealed, exact-question `study/frozen-questions.json`, its SHA-256 file `study/frozen-questions.sha256`, and `study/first-answers/` for locally downloaded responses. Private labels and questions stay in the local manifest. The script will refuse to overwrite a nonempty existing study directory. The SHA seal catches accidental changes but is **not** a cryptographic proof of when or by whom the questions were frozen.

## Run the first answers deliberately (not automatically)

1. Open the **installed** HomeBrainOS v2 add-on → **Ask / Chat**. Record its displayed installed version and configured model separately; GitHub `main` does not establish the installed version. Prefer a **server-enforced read-only upstream MCP token**, not merely the words “do not change anything” in a question. Otherwise, do not attempt the real acceptance run.
2. For each private question in `frozen-questions.json`, use **New conversation**, paste the question **exactly once** into Ask and submit it. Do not coach the model, repair the prompt, retry a failure, use a preceding conversation or mix sources from other questions.
3. After that single first response, choose **Technical details → Download JSON** in Ask. Save or rename the unedited export under `study/first-answers/sr-01.json`, `sr-02.json`, ..., `sr-10.json`. A failed first answer is still a valid first-attempt observation and must **not** be replaced by a later successful retry.
4. Keep all raw Technical JSON and device names private. Use no live control tests, create no rules and do not operate the model as an unattended sweep. Each Ask question is a user-initiated normal inference; cloud-backed configurations may incur cost.

The ten cases cover: hub status; battery inventory; brightness history; environmental readings; current heating states; restart causes; installed automation settings; energy-total history; contact-history coverage; and diagnostic-log limitations. These are deliberately not the six previously unblinded fictional scenarios. Actual answers and relevant source truth are **not** prefilled.

## Verify integrity and capture coverage — still entirely offline

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py verify --directory "C:\\Private\\HomeBrain-Acceptance\\study" --output "C:\\Private\\HomeBrain-Acceptance\\study\\capture-report.json"
```

The checker rejects modified/unsealed manifests, mismatched question text, malformed Technical JSON, and duplicate request IDs. It reports missing case IDs, detected prior conversation-source use, attempted device-command records, and whether exported model fingerprints / add-on versions are consistent. It also uses the existing privacy-preserving offline audit, which counts native tool/contract receipts. **Neither transcript contents nor a “no prior receipts” indication proves that a session was genuinely fresh, read-only or source-real; those must be attested independently.**

If a review is to be applied, **all ten** frozen cases must have their first answers present and there must be no reported prior-receipt carryover or attempted device command. Create a separate private human review file in the existing `homebrain-v2-source-real-human-review.v1` format (see [the measurement milestone](HUBITAT-MCP-AI-V2-NEXT-MILESTONE.md)). Its `export_index` uses the `captured_case_ids_in_review_order` from the completed capture report; with all ten cases present this is `sr-01` through `sr-10`, zero-based.

```powershell
python hubitat-mcp-ai-v2/tools/source_real_acceptance.py verify --directory "C:\\Private\\HomeBrain-Acceptance\\study" --reviews "C:\\Private\\HomeBrain-Acceptance\\private-reviews.json" --output "C:\\Private\\HomeBrain-Acceptance\\study\\reviewed-summary.json"
```

The optional reviewer must explicitly count supported factual claims and unsupported definitive causes using the **actual native receipts**. A tool returning successfully, a low number of warnings, or a history query returning zero rows **never automatically passes** answer quality. The safe report includes only fixed public case IDs, summary counts and pseudonymous evidence metrics; no raw device labels, question strings, untrusted tool text, filenames, receipt payloads, private notes or credentials. A reviewer should separately check group membership, attribute meaning, historical window scope, command-versus-state distinctions and alternate explanations. The script cannot establish reviewer independence from the export alone.

## Decision gate after collection

The existing model-led v2 agent and generic production prompt remain unchanged until this fresh baseline is captured and reviewed. Break missing/incorrect results down by tool-schema errors, failed target discovery, absent discriminating reads, incomplete historical scope, interpretation errors and unsupported causal claims. Only then design **one** general change, compare it prospectively on a **different** unseen set under the same model/schema and require an improvement in **causal calibration** without loss of safety. Do not reuse either these future source-real cases or the old fictional holdouts to claim independent confirmation after tuning.

**Limitations:** This is a frozen capture protocol and independent local verification tool; it has not run HomeBrain, inspected live Hubitat history, confirmed read-only permissions or scored any genuine household answer. `source_kind: "real"` in the human review is a **reviewer attestation**, not an automatic truth claim. No production add-on version bump is necessary for this offline-only tool.
