# v0.18.259 — Recover historical input events before concluding sensor visibility is missing

## Live v0.18.258 finding
HomeBrain correctly recovered 20 source-timestamped switch reports for the two Bathroom lights and distinguished unrelated Shower app notifications from app 4013's verified brightness commands. However, the model queried several independent upstream/input IDs (including the occupancy device 7895) and their native current-history replies contained no usable events. HomeBrain stopped with the input history marked unavailable although the same local Historical Journal already captures motion, occupancy, presence and button events as well as switch.

## Architecture: one bounded fallback in the original model's read loop
- After the original model independently selects and executes a successful, device-scoped event-history read with **no usable incident-time input rows**, the existing read-only Historical Journal may be queried for **at most three of those same IDs**.
- Each query uses the independently verified incident date/time bounds, an exact device ID and a 160-row cap. No unscoped scan, guessed ID or additional MCP permission is introduced.
- Project **only motion, occupancy and presence** source-timestamped values into the original agent's shared input evidence packet; do not promote the journal's collector reception clock to the event clock. Genuine source timestamps are deduplicated and provenance is retained.
- Preserve archived collector-only counts, connection gaps and per-device missing-history coverage separately. An empty journal query does not prove inactivity.
- The original model checkpoint and final Historical Journal digest now carry archived input evidence, enabling genuine temporal comparisons without asserting that an observed input triggered a particular action or app.
- An archived input report does **not** contain Hubitat's `triggered[]` app-notification metadata, so it must not produce invented dependency graph edges.
- The recovery can run after the model's input history read and is idempotent by request-local typed evidence receipts. No background tasks, automation writes, new tool routes or live device changes.

## Validation and remaining gap
Tests cover positive source-time recovery, reception-only exclusion, empty-history idempotence, strict original ID scoping, malformed timestamps, unrelated journal attributes and incomplete historical coverage. No claim is made that every missing historical input is retained; results depend on the already configured journal's capture period and gaps. This adds source recovery and model-facing evidence; the upstream initiating controller remains unverified until its original execution source is independently observed.

Full repository CI must pass before merge. No live Hubitat or HA add-on update is performed.
