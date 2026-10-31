# v0.18.272 — Natural incident stories with verified sensor names and cycle timelines

## Report from v0.18.271 live testing

The model correctly investigated the five ON/OFF cycles of Bathroom Lights 1 and 2, found complete 5/5 reception pairing for sensor 7895, and published an evidence-safe short explanation. However, the text continued to refer to "input device 7895" and compressed all ten source-timed state changes into one long paragraph. Users could not quickly see when each light cycled.

## Architectural correction

- In `tool_executor.result_details`, retain a bounded, sanitised `deviceName` from a successful and exactly scoped `hub_list_device_dependents` response alongside the existing whitelisted app IDs. Do not retain arbitrary settings or other device metadata.
- In the source evidence bridge, carry independently verified input-device labels into the final incident facts only when the successful dependency-read ID equals the observed response ID and an independent input history was checked. A label lacking that chain is never invented.
- Add a pure `causal_incident_narrative.py` component. Device names are filtered for unsafe control/markup characters. Each light's source-timed ON/OFF stream must alternate correctly, agree with the other light, and match every transition within two seconds before a paired-cycle timeline is rendered.
- The publisher now begins with the practical cause hypothesis and a named sensor where verified, followed by a three-column ON/OFF/duration timeline (up to twelve rows; counts retained and omissions noted), a concise named-app brightness observation, and one paragraph about what is still unknown.
- When the user asks to compare competing hypotheses, the alternative sensor comparison uses independently sourced names and plain language instead of raw numeric IDs and mixed-clock jargon.
- The source-only brief and fully claim-attested publication share the same renderer. Missing/invalid structured claims do not change the evidence safety fallback. An original initiating controller remains unknown without command records.

## Regression gates

Synthetic five-cycle source timeline, exact independent sensor-name projection, safety of mismatched/unsafe labels, omitted or reordered source switch rows, nonmatching inter-light stagger, named alternatives, no controller inference, renamed IDs, and existing claim-attestation safety tests. No new MCP calls, model rounds, tool permissions or Hubitat/HA writes.

## Acceptance

On the identical read-only bathroom investigation, show the actual label of device 7895 if provided by its scoped Hubitat dependency read, with a readable five-cycle table and a single plain-language uncertainty statement. Historical change times must come from source-qualified switch reports only; motion comparisons remain labelled as collector-reception correlation.
