# V2 alpha.148 receipt grounding and prospective acceptance

The alpha.145 installed cohort remains the exposed baseline. It missed the
usefulness and unsupported-definitive-cause gates. Alpha.148 adds bounded
grounding anchors to the existing receipt review and final audit. The anchors
distinguish the reporter, notified apps and command issuer on each source row,
provide independently formatted UTC and hub-local timestamps, and keep log
matches, returned rows and scope-unspecified totals distinct. The source-only
fallback can surface notified listeners without identifying them as initiators.
The changes add no new model round, MCP call or native write path.

For a fresh installed evaluation, configure the dedicated Read ON / Write OFF
client. Open **Acceptance study** in alpha.148, enter the eight exact labels,
and seal the `alpha148-prospective-v1` pack. Capture each of `a148-01` through
`a148-10` once and run offline verification. The new study uses its own data
directory. The CLI still verifies the original alpha.145 pack unchanged.
Keep both cohorts private. Use the same independent claim-review rubric and
promotion thresholds specified in the alpha.145 acceptance procedure. The
alpha.148 cohort is pending capture and grading.
