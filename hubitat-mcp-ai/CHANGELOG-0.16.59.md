# Hubitat MCP AI 0.16.59

## Log grounding and performance-source consistency

- Successful `hub_get_logs` reads now satisfy the request-local log grounding latch whether they are direct, routed through `hub_read_diagnostics`, or routed through `hub_manage_logs`.
- A successful `hub_manage_logs -> hub_get_logs` call can no longer trigger a redundant log-evidence retry merely because the gateway name differs.
- The API serialization boundary now rejects final claims that hub metrics, performance statistics, or logs were not returned when successful current-turn receipts prove those sources were read.
- Performance synthesis recognizes `Recommended Improvements` as an action section and grounds quoted wording such as `"polling" intervals` before configuration matching.
- Generic implementation claims such as `blocking calls`, `pause other hub activities`, synchronous HTTP/network-timeout explanations, and `non-blocking` driver prescriptions are localized unless the relevant implementation or configuration was read.
- Unsupported app/rule implementation advice such as complex-loop, external-API, or triggered-by claims is inspection-first without same-turn implementation/config evidence.
- Common Markdown labels such as `**Hypothesis:**` and `**Action:**` are parsed correctly inside action bullets so mechanism hypotheses receive the same grounding as analysis text.
- Unsafe configuration recommendations are replaced as whole actions before sentence splitting, so examples such as `e.g. 65W for 2 minutes` cannot leave an unsupported trailing fragment behind.
- Already-localized sensor/configuration guidance is not reclassified by a second generic pass, preserving the sensor-specific 0.16.54/0.16.55 contracts.
- Adjacent duplicate inspection-first guidance is collapsed while measured performance facts remain intact.
- No additional Hubitat reads are introduced.

## Live regression coverage

Regression tests reproduce both 0.16.58 live outputs: the performance-only LG/SenseCap/MCP wording and the successful metrics + performance + 100-log turn that incorrectly ended with a `no data` answer. Existing performance grounding contracts remain covered by the full release suite, including the 0.16.54/0.16.55 sensor-specific guidance paths.
