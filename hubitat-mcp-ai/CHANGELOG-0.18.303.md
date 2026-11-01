# HomeBrainOS v0.18.303 — Stage 7.1: negative-evidence scope and causal-question coverage

This is a **synthetic-only, after-the-fact independent reviewer aid**. It does **not** change the model's READ/STOP investigation, final answer schema, agent planner, model provider, production publisher, Hubitat/HA device access or automation.

## Evidence motivating Stage 7.1

The user's real **Two apps issue competing commands** Stage 7 run produced:

- Three of three reference-relevant sources read, all required finding types covered, eleven of eleven declared source field values matching.
- Recorded OFF command at 23:10:27 from the fictional Inactivity App and setLevel(40) at 23:10:29 from the Button App; device OFF report received at 23:10:30.
- A fifth sentence: “There is no physical confirmation that either command was successfully executed.” Its model-supplied claim type was \`absence_proven\`, which the strict typed validator necessarily flags as high risk. The sentence is *reasonable if scoped to the inspected records*, but the supplied records cannot prove that no physical confirmation exists elsewhere or that neither command physically executed.

This shows a genuine **quantifier/scope** question, not just an incorrectly formatted JSON envelope. Treating a missing physical-ack record as a universal negative would be unsound; forcing the model's free prose into an automatically “supported” verdict would also be unsound.

## Implementation

### Host-derived, bounded review of source coverage

- New \`stage71_evidence_scope.py\` produces an explicit post-run view of the exact **model-inspected records** versus **all supplied fictional fixture records**.
- For each, list source IDs, recorded state/telemetry IDs, command/decision IDs, true positive acknowledgements (\`physical_acknowledgement is True\` or \`device_confirmation is True\`), records explicitly marked \`False\`, and separate \`coverage_gap\` records.
- Always distinguish **not recorded in the examined set** from **not existing at all**. None of the present synthetic fixtures establishes full real-world history completeness, proven global absence, physical nonexecution, or uniquely identified command→physical-effect causation. Even a positive acknowledgement record does not automatically prove a unique cause.
- Full fixture evidence is revealed only after Gemma has finished and cannot alter the source-recall grade or model's earlier decisions. No hidden gold source-selection labels are placed into the model prompt or reviewer packet.

### Independent causal-question review

- The reviewer, rather than the answer author, assesses four generic obligations: reported observations, recorded actions, causal attribution, and physical-operation / negative-claim scope.
- Each **sentence** retains its Stage 7 factual review and gains an optional human verdict on absence-claim scope: not a negative, appropriately limited to examined records, overstates global absence, or ambiguous.
- Per-question coverage is **Not reviewed** by default, with addressed, omitted, explicitly unverifiable, or unclear options. An answer cannot be marked “independently reviewed by human” until all original factual, scope, question-coverage and completeness/caution controls are manually assessed.
- The revised explicitly copied JSON review packet contains the original fictional evidence plus any optional local human ratings. No automatic write, model call, third-party submission, or credential exposure.

## Validation, caveats and next test

Mock-only tests cover the exact competing-commands fixture, the difference between missing acknowledgement and proven absence, skipped coverage records, an invented positive receipt in an unread fictional source, false physical-causation language despite correct source atoms, invalid source IDs, redacted arbitrary secrets and no production-module dependency.

**Do not mistake this for automated full-prose verification.** The host scans only the bounded synthetic evidence types; humans must still judge the language and question coverage. The previous strict \`absence_proven\` typed citation gate remains unchanged; Stage 7.1 supplies the missing *scope review*, not a blanket exception. Publisher approval always remains false.

Update the Home Assistant **Hubitat MCP AI** add-on to v0.18.303. Stage 7.1 appears in the Stage 7 reviewer panel after a successful Stage 6 synthetic investigation. Run **Two apps issue competing commands** only if another consented cloud test is desired (maximum four model requests using the current account), open the full fictional source packet, and assess each sentence's negative-claim scope and the four causal-question obligations. Stage 7.1 itself makes **zero extra cloud requests**.

No live home systems or actual device records are involved. GitHub CI uses mocked model transports only. Rollback is v0.18.302.
