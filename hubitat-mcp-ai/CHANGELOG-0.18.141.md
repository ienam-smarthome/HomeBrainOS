# HomeBrainOS v0.18.141 — measurement-scope intelligence (opt-in V2)

## Architectural change

Current V2 power and energy queries now distinguish the *quantity* (W or kWh)
from the *physical coverage* of the meter (whole site, circuit subtotal, one
individual load, unknown). This is a general typed data model, not an Octopus
brand or individual Hubitat device-ID exception.

- The existing one-pass semantic model may optionally propose measurement
  roles for a bounded list of devices discovered from the live inventory.
  Every role must match an authentic inventory ID and exact label; model
  interpretations are marked **unverified**, not silently treated as source fact.
- Structured Hubitat measurementScope/meterRole metadata takes precedence over
  model inference. Optionally, an operator may confirm roles once in the add-on
  `v2_measurement_roles_json` configuration, e.g. `{"1234":"site_total","5678":"individual_load"}`
  using IDs from the real inventory. This starts empty; no meter roles are
  hard-coded, and invalid/non-current device IDs fail closed.
- Individual-load top/bottom power and energy rankings separate whole-site and
  circuit subtotal meters to avoid overlap, disclose uncertain measurement
  scopes and label AI-inferred roles as provisional. Mixed or uncertain totals
  and averages are **withheld** rather than double-counting meter hierarchies.
- Canonical units stay distinct: power in watts (including conversion from kW)
  and accumulated energy in kWh (including conversion from Wh). Incompatible
  units are never silently treated as correct.
- Devices lacking a reported measurement are distinguished by whether they
  advertise an appropriate meter capability, rather than declaring every
  light, sensor and controller an unhealthy/unresponsive power meter.
- Regression fixtures cover a site meter, circuit subtotal, appliance loads,
  explicit confirmed roles, malicious/unknown model IDs, unit conversion and
  overlapping-total refusal.

## Boundaries

The screenshot of Hubitat `00 Energy Usage` is a benchmark: at the recorded
snapshot, site power was 187 W, individually metered total 79 W, and remaining
unmetered/other 108 W. Today's energy was 6.23 kWh site total, with 3.22 kWh
metered and 3.01 kWh unmetered. These values must **not** be treated as
current live data or added twice. V2 does not yet consume that app's private
energy ledger or claim that its inventory metadata classifies every meter.
Normal production V1 and all Hubitat writes remain unchanged.
