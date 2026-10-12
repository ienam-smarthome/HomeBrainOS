# 0.17.2 — Evidence-led lighting decisions after proven commands

HomeBrain previously stopped at the confirmed `setLevel()` command producer for a custom lighting application because the deeper decision follow-up recognized only app display names containing “lighting” or “low light.” Its confidence about *which app sent the command* was correct, but the explanation of *why that app acted* was incomplete.

## Adaptive command-to-decision investigation

- Select the existing bounded rule-decision follow-up from **verified command semantics**, not a literal app display-name convention. Stateful custom app names such as `Bathroom (💡 Lights On, 🏃 Motion Active)` now qualify when their confirmed `setLevel(30)` command changed a light from OFF to ON.
- Preserve the device event and the command producer as authoritative. Configuration and sensor timing can supplement that fact but cannot replace it or establish who pressed a button.
- Inspect the producing app's configuration and tightly scoped logs. If they do not establish the trigger, correlate at most two explicitly configured motion/occupancy source histories or one unambiguous same-room occupancy source.
- Compare the sensor's reported active edge against the actual ON boundary. An event reported **after** the light changed is not described as a proven upstream trigger.
- Reuse already fetched light command and switch history to distinguish previous level-at-activation commands from a later `setLevel()` adjustment during the same ON interval. Different observed levels suggest, but do not prove, a configured time-of-day schedule.
- Extend configuration excerpts to expose available brightness, dimmer, level and schedule information.
- Preserve the simple button/switch fast path, read-only evidence acquisition, and bounded investigation budget.

## Regression coverage

- Custom lighting producer name and `setLevel` attribution for Bathroom Light 1 at 07:08:06, 12 October 2026.
- Earlier 02:53 (10%) and 06:45 (30%) level commands, duplicate commands around one switch-on, and later 07:15 (50%) dimming.
- Unique versus ambiguous occupancy-source selection and source configuration precedence.
- Correct after-boundary timestamp language and no inferred sensor causation.

This release changes HomeBrain code only. Hubitat apps, rules and device states are not modified.
