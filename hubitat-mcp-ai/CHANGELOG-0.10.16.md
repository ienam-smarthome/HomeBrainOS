# 0.10.16

- Device-choice clicks now submit a complete deterministic command such as
  `turn on Dehumidifier 2`, rather than the context-dependent text `2`.
- Existing pending choices still resolve directly to their stored Hubitat device IDs.
- If pending state was lost after a restart, expiry or session change, the complete
  clicked command is safely re-resolved instead of being sent to Ollama as a bare number.
- Browser requests now include the stable session ID in both the JSON body and header.
