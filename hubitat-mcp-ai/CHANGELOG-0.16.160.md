# 0.16.160

- For room-filter results, explicitly offline device motion/presence and environmental readings are separated into `stale_states` rather than described as verified current states.
- Preserve the original reported values in diagnostic evidence alongside health and connectivity warnings.
- Update regression assertions for the Seeed Studio MR60BHA2 (device 7304) to confirm its retained motion, presence and 8.7-lux readings are excluded from current room-state fields.

Scope: this change safeguards `homebrain_filter_devices` room evidence. Direct `hub_list_devices` responses and all possible free-form model summaries are not yet deterministically constrained by this change.

Read-only; no device controls altered.