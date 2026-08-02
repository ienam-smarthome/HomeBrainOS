# 0.10.308

- Fix named-device resolution so device names are no longer passed into Hubitat's status-only `filter` parameter.
- Resolve named devices from one authoritative complete-inventory read before inspecting requested attributes.
- Preserve exact device attributes on the resolved target, including battery readings.
- Reject fuzzy matches that agree only on a generic device-kind word such as `meter` while preserving safe typo tolerance.
- Update rule-authoring and device-history regression fixtures to the complete-inventory resolver contract.
