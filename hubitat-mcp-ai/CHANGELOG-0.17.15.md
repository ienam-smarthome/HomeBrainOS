# HomeBrain 0.17.15 — Independent ON and OFF causal provenance

The 0.17.14 Bedroom 1 investigation correctly identified a likely external Hue dimmer turn-on, the directly observed post-ON setLevel(45) command from App 4015, and a 69 ms correlation between FP300 inactivity and the light switching OFF. It still labelled the OFF event “likely triggered by motion inactivity” without first obtaining independent OFF command provenance. The available app configuration described a longer inactive-delay rule, and no OFF-command source had been established.

## Architecture

- **Treat each state transition as a separate hypothesis.** The generic source-scoped causal graph now exposes `transitionEvidence.on` and `transitionEvidence.off`, each with distinct observed state, direct command, candidate trigger, configuration/log context and confidence. ON's command producer, sensor and app can never silently become OFF's.
- **Independent focal OFF read.** For a deep investigation of a unique, bounded ON interval, the host checks the same exact device's `command-off` event history (one bounded 168-hour page, maximum 50 rows) before the ON command/bridge fast paths return. The lookup is skipped if compatible direct OFF command provenance was already available; no hub/device action is executed.
- **Separate app context.** When an OFF command identifies an app, its configured settings and OFF-time execution logs are checked as distinct evidence from the ON app's context. Where OFF command ownership is unknown, at most one relevant `lightSwitchHandler` app log is checked as a *notified listener*, not promoted into a command-producing automation. Failed/zero-row results remain source limitations.
- **Confidence calibration.** Direct OFF command provenance establishes the immediate producer, but not the initiating timer/motion condition. Without a proven OFF command, proximity to an inactive sensor remains `temporal-sensor-correlation-only` or `observed-off-with-unidentified-initiator`. `triggered[]` proves event notification, not action causation.
- **Shared synthesis verification.** Final answers are instructed to explain ON and OFF separately. A common causal verifier blocks unsupported statements that an OFF event was probably triggered by sensor inactivity merely because timestamps are close; preserves independent ON attribution and valid cautious descriptions. The correction runs both during synthesis and in the final API response.
- **Instrumentation.** Added `causal_off_provenance_reads`, `causal_off_command_reused`, `causal_off_app_log_reads`, and `causal_off_app_config_reads` to the request metric vocabulary/presenter.

## Bounded evidence and safety

An empty `command-off` page does **not** prove that Hubitat, Hue, Aqara, Matter or a person could not initiate OFF; it only proves that the bounded query returned no matching command rows. Event history remains subject to source integrity and page limits. App configuration is current and is not proof a historical inactivity timer ran. A native bridge/third-party automation requires its own execution/configuration source for definitive attribution.

The host-side reads remain read-only and are limited to the user's uniquely identified closed interval. The optimization retains direct final synthesis when the requested ON investigation is otherwise evidence complete; no exploratory room-wide fanout was added. Test results and live speed must be assessed separately.

## Regression coverage

Tests cover zero-row vs failed OFF-history reads; separate app command producers; a previously observed OFF command being reused; scoped OFF app logs; a physical bridge-state reporter and downstream app listener; open or ambiguously dated intervals; preservation of a well-grounded ON explanation; and prevention of overconfident OFF-trigger claims in prose and tables.
