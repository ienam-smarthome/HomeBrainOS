# Hubitat MCP AI v0.18.212 — General operational evidence survives model publication

## Actual 29 October general question live failure

A newly admitted Native V2 general-purpose question asked which Hubitat devices were currently offline or stale, what recent activity showed, which apps depended on affected devices, and what needed attention. Native V2 obtained 10/10 successful read results in 40.668 seconds, including `hub_get_device_health` reporting 51 stale + 1 unknown activity and four targeted `hub_list_device_dependents` reads. It then published **only** virtual device 7681 `switch=off`; `claim_publication.status=no_valid_claims` (`invalid_item`) and an 7.887s final claim-selection model pass discarded the returned health and dependencies. Two `hub_get_device` proposals on `hub_read_diagnostics` were correctly rejected as not independently discovered. There is no evidence that all the 51 were physically offline; app reference counts do not demonstrate execution or faulty automations.

## Reusable evidence-system improvements

- Introduce `native_operational_evidence.py`: bounded, typed, receipt-verified operational facts from **any** `hub_get_device_health` and `hub_list_device_dependents`. It accepts only genuine projected numeric device/app IDs, safe source labels and returned lastActivity values; does not hallucinate offline status, automate remediation, classify a silent device as definitively failed or attribute breakage to referencing apps.
- Connect operational facts to the shared factual ledger and generic claim catalogue. Health-sample counts, reported stale/unknown entries and identity-matched dependency app references can now be selected with the **same source claim protocol** already used for state, logs and runtime metrics. A source report with missing/untyped arrays is not fake zero or proof of health.
- Ensure general-purpose host publication retains at least the material health/relationship *source classes* when the model chooses a marginal single fact. When the model returns an unsupported structured item, the host selects a bounded set of verified representatives across **different evidence kinds**, rather than publishing a meaningless unrelated switch observation alone. This is evidence-kind diversity, **not** question word or device-specific routing.
- Improve generic source highlights so live device-health counts and app references reach the final selection and diagnostic transcript, instead of `summary={}` plus unexplained operation names.
- Add multi-source synthetic replay regression tests for 51-stale/1-unknown, dependency identity mismatches, model fallback, valid-but-unrepresentative model selection, incomplete health arrays, bounded coverage and source display sanitisation.

## Limits and next stages

This release preserves read-only Native V2, its independently checked live MCP permissions and all write safeguards. It **does not** establish actual connectivity for stale devices, or that any referenced app is broken. It improves generic factual coverage and safeguards but does **not** finish open-ended Claude-quality reasoning; next stages should provide objective-aware analysis, broader trusted evidence kinds and concise source-grounded narrative synthesis, validated across unrelated question fixtures.
