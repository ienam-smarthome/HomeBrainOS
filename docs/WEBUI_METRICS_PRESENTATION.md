# WebUI request-metrics presentation

`technical_metrics_presenter.present_request_metrics` is the presentation boundary between the privacy-safe metrics returned by `/api/ask` and the browser technical-details panel.

The presenter:

- accepts only a mapping;
- renders only the fixed counter and duration vocabulary;
- omits zero counters and unavailable durations;
- formats sub-second values as milliseconds and longer values as seconds;
- accepts only the known outcomes `success`, `failed`, and `cancelled`;
- ignores every unknown key.

Ignoring unknown keys is intentional. The WebUI must not turn arbitrary response fields into labels because those fields could contain prompt text, device names, session identifiers, tool arguments, credentials, or other private data.

The current PR adds and validates the presenter. A subsequent narrow wiring change will call it from the existing technical-details rendering seam without changing the raw expandable response JSON.
