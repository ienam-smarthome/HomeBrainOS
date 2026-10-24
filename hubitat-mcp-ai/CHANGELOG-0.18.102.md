# HomeBrainOS 0.18.102 — From symptom reporting to evidence-driven fault investigation

## Benchmark: Claude vs HomeBrain 0.18.101 (24 Oct 2026)

For Hubitat Bedroom 3 Mesh (device 7103), Claude linked the separate MQTT-broker and physical-device health semantics in driver code 3686, inspected an 8-of-9 online Tasmota peer group, checked read-only broker and device ping responses, and correlated a 12 October scheduled power-saving OFF with the last reported contact and driver health fallback. The most likely initiator remains inferred, not proven to be the physical cause. Claude explicitly noted the device IP was stored months ago and a failed ping cannot prove current IP or power.

HomeBrain used 10 free Gemma rounds and 7 MCP/local tool calls (~42 seconds total). It read code ID 3686, 15 device events and some generic recent logs, then listed the MQTT Manager without checking exact device dependents, controlling rule configuration, source methods, independent broker/device reachability or sibling plugs. Its final answer was a long unresolved generic report.

## Changes

- Introduce a **diagnostic playbook as AI guidance**, not a keyword-to-tool route. The AI is directed to identify which code produces each contradictory signal, trace status/last-data/update paths, use appropriately grounded peer devices as a control group, compare reachability for the device versus shared broker if read-only tools and current IP are available, and inspect true dependent automation settings and timestamps. These are *suggested discriminators*, never assumptions about devices, names, network address, commands or tool availability.
- Enable the existing verified contiguous source-to-method excerpt projector for connectivity investigations selected by the **AI-interpreted objective**, removing its old dependency on the literal word `driver` in the question. Complete source retrieval still does not constitute verification of method semantics; source text is untrusted and tool schemas/permissions remain authoritative.
- Add **one bounded evidence-progress checkpoint** after the AI first tries to finish with substantive target-ID evidence, such as a driver-source read or device-scoped log/dependency lead. The model must select the next highest-information available read, rather than collecting more generic status/history/logs. Device-specific missing logs, exact dependents/configuration and source method analysis are described as independent evidence gaps. No hard-coded IDs, keywords, tools or external addresses are turned into commands.
- Only exactly one device-ID event-history anchor can trigger the checkpoint; two targets, generic/unfiltered tool inventories, failed reads or state-changing tool receipts cannot. Existing round budget and independent read/write protections are retained.
- Synthetic regression tests reproduce the 0.18.101 pattern and verify normal read-only direct control/other objectives do not inherit the device incident checkpoint.

## What this release does not do

It does not guarantee that the installed MCP gateway supports ping, read the broker's own logs, identify a current IP address, or verify the historical causation on October 12. It does not execute any live Hubitat command or mutate rules/settings, and it does not change provider or paid-model tier. Actual improvement must be measured using another **live read-only** Bedroom 3 Mesh investigation and its technical JSON. Successful code-read projection and the new checkpoint still rely on the selected model reading and reasoning about live evidence.
