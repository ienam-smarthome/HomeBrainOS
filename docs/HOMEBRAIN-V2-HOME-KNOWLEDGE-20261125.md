# Home knowledge, briefing and argument guard (alpha.187)

Why: five question-set runs kept re-deriving what the home contains (what is a light, what heats, which sensors exist) and made avoidable read errors. The hub log confirmed two causes: `attributeNames` rejected with `format: detailed`, and responses over 99,500 bytes (108,683 seen repeatedly).

- `home_knowledge.py` — `HomeNotes` (owner text in `/data/homebrain-v2-home-notes.txt`, 3000 characters, plain text), `profile_text` (device class lists from the same inventory snapshot as System Health, via `home_overview.summarize_device_inventory().profile`), `HomeKnowledge.context()` (labelled: notes are owner statements, profile is an earlier snapshot), `briefing_text` and `BriefingSchedule`.
- The agent appends `context()` to the system message. Nothing reads or interprets the user's question.
- Briefing: `GET /api/briefing` on demand; `briefing_enabled` + `briefing_time` (hub timezone) send it once a day through the network-alert notify path; retried for 3 hours if delivery fails.
- `receipt_compute.normalize_list_devices_args`: from the call and live schema only; reported to the model as `client_arg_adjustment`.
- Not yet measured live: round/accuracy effect of the context block; briefing delivery to a phone.
