# 0.16.52

Performance diagnosis now keeps the model's useful hypotheses separate from proven causes even when the raw log result is larger than the final evidence receipt.

## Fixed

- Preserve compact Rule Machine threshold samples from the **full** `hub_get_logs` result while keeping the ordinary evidence receipt bounded to its first 20 log rows. This prevents the provider from seeing a 100-row threshold sample that the final host guard can no longer audit.
- Prefer the structured full-result threshold sample over the retained excerpt. If the complete sample contains a crossing, the guard does not incorrectly classify the excerpt as one-sided.
- Reject claims such as `fluctuating around the 65 W threshold` when the full sampled values remain on the same qualifying side of the trigger.
- Downgrade log-to-performance wording such as `a likely hypothesis for the high busy percentage` or `hidden overload source` to an explicit hypothesis unless current-turn evidence directly links the observed activity to the measured performance statistic.
- Block broader ungrounded Rule Machine prescriptions such as `needs a debounce` or `larger gap between trigger actions` when the turn has not read the actual rule/app configuration.
- Keep legitimate investigation advice intact: measured busy %, call counts, latency, state size, staleness, repeated warnings, and log volume can still be reported directly; possible reconnect timeouts, over-polling, retry overhead, and serialization cost remain useful hypotheses to verify.

## Regression coverage

- Reproduces the 0.16.51 TV performance case where the relevant Rule Machine rows occur after the 20-row evidence excerpt.
- Verifies that an `Action: Wait for event ... 0:03:00` timer is not parsed as a power value.
- Verifies that full-result threshold crossings override a misleading one-sided excerpt.
- Adds a Claude-style LG webOS TV example to ensure stale + slow calls can motivate a reconnect/timeout investigation without being presented as a proven overload cause.
