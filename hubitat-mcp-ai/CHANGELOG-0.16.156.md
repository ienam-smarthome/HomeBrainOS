# 0.16.156

- Reconcile Living Room diagnostic device health when compact Hubitat context lacks driver-specific health fields.
- Restrict additional reconciliation to diagnostic candidates instead of all room devices, preserving the fast path for ordinary sensors.
- Qualify missing health coverage rather than assuming devices are healthy.

This release is a candidate pending complete green CI and live validation. No device controls are changed.
