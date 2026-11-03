# v0.18.378 — Honor explicit native Rule Machine document reads (read-only)

## Live observed failure / baseline

The user manually proved a trigger-less Rule Machine Delay 0:02:00 followed by virtual switch OFF; event provenance links OFF state and command records to the test rule. To discover *native authoring field/action* shape, they twice asked HomeBrain to call `hub_set_rule(operation="read", rule_id=<existing rule>, args={"sections":["actions"]})`.

Installed v0.18.377 instead returned the same generic multi-paragraph partial verification answer. The second diagnostic packet showed 15.7s, 5 model rounds, 6 tool calls, `read_only_model_write_blocked=1` and a host `typed_native_rule_document` receipt marked `success:false` after calling the **all-sections** document prefetch without `args.sections`. Its receipt only said `Native rule document unreadable or incomplete` even though the requested operation is supported upstream. The packet doesn't contain the true remote tool failure. The host all-or-nothing projection conflates source read failure with rejected/unsupported document shape; this is not proof that the test rule or native actions are invalid.

Upstream `libraries/mcp-native-documents-lib.groovy` implements `hub_set_rule(operation="read")` and allows explicit sections. In upstream's action read, ordered rows are `{id, value:{method,...}}`. The existing offline writer candidate was aligned in PR #1342, but the **running agent's routing** still failed the specific read request.

## Change

- Recognise **explicit caller-selected** `hub_set_rule operation=read` requests with **one exact numeric rule_id and a parsed finite allowed sections list**. Questions about why a rule ran or proposals for writes stay on their existing paths.
- Execute the exact `hub_set_rule(read)` envelope directly via an available installed gateway only after the structured tool-effect classifier confirms **READ**. Never send a create/update/form/start/pause/delete operation, guess a gateway, or perform an automatic retry.
- Return verified ordered action IDs and `value.method` from the native response. Other requested sections report only bounded safe setting values or counts, not guessed action semantics. In particular, a successful *actions-only* read is **not** falsely advertised as complete configuration or proof of delayed device execution.
- Distinguish **tool/source failure** from a successful call with **incomplete or mismatched native document data**. Show a bounded, credential-redacted error code/message and actual selected gateway in the answer **and** evidence receipt. A failed read is not proof of an absent rule.
- This deterministic source retrieval bypasses unrelated model planning and generic all-sections verification finalization **only for an explicit, validated read call**. Ordinary existing-rule investigations and the model's read-only/write safety gates remain unchanged.
- `tests/test_explicit_native_rule_read_0_18_378.py` covers positive real-source-shaped action documents, exact allowed input, duplicate/malformed/missing action IDs, source error, timeout/exception, mismatched target, partial/paged response, settings redaction, no gateway and no mutation calls.

## Expected outcome and honest limitations

**Expectation (not yet live measured):** HomeBrain will give a short, independently sourced action-method list or the actual tool error for the same explicitly requested operation, rather than another broad unresolved report. This should use one MCP read and zero Cloud model rounds on the direct route. These are design/test expectations; installed user upgrade and observed route/timing are **NOT YET VERIFIED**.

**Still blocked:** no production integration or enabling of the `scripts/native_rule_delay_candidate.py` writer, no actual MCP-created rule BAT, no reboot survival proof, no automatic cleanup, no real Internet block schedule. Native date trigger support is still limited per upstream issue #575. This release does not modify any live Hubitat or HA devices, rules or preferences. As always, exact-head CI is required before merge; green mock tests cannot certify real MCP server behavior.

**Rollback:** revert the explicit source read path and return to normal model-selected inspection. The old path can conceal failed MCP reads, so retain source error evidence if reverting.
