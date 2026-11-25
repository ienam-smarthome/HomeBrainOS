# Home knowledge, briefing and argument guard (alpha.187)

Why: five question-set runs kept re-deriving what the home contains (what is a light, what heats, which sensors exist) and made avoidable read errors. The hub log confirmed two causes: `attributeNames` rejected with `format: detailed`, and responses over 99,500 bytes (108,683 seen repeatedly).

- `home_knowledge.py` — `HomeNotes` (owner text in `/data/homebrain-v2-home-notes.txt`, 3000 characters, plain text), `profile_text` (device class lists from the same inventory snapshot as System Health, via `home_overview.summarize_device_inventory().profile`), `HomeKnowledge.context()` (labelled: notes are owner statements, profile is an earlier snapshot), `briefing_text` and `BriefingSchedule`.
- The agent appends `context()` to the system message. Nothing reads or interprets the user's question.
- Briefing: `GET /api/briefing` on demand; `briefing_enabled` + `briefing_time` (hub timezone) send it once a day through the network-alert notify path; retried for 3 hours if delivery fails.
- `receipt_compute.normalize_list_devices_args`: from the call and live schema only; reported to the model as `client_arg_adjustment`.
- Not yet measured live: round/accuracy effect of the context block; briefing delivery to a phone.

## Alpha.188: ground-truth self-test

The 10-question run measured speed and errors only. It now also compares five answers with `/api/overview` (the deterministic inventory snapshot) read before and after each question: named devices present in both snapshots must appear in the answer; an empty expected set requires the answer to say none; the stale-device count must fall within the hub's before/after range ±3. Answers about memory, CPU, restarts and "what changed" are not checked (no inventory ground truth) and show no hub check. The text matching lives in the self-test harness, not in the agent. Repeat 3× to see run-to-run variance. Limits: names are matched by substring; the check proves recall of what the hub reports, not that nothing extra is claimed.


## Alpha.189: proactive home alerts

`HomeWatch` (home_knowledge.py) reads the same read-only inventory snapshot as the briefing every 5 minutes (off by default, `home_alerts_enabled`).
Water wet alerts immediately; an open contact alerts after `home_alert_open_minutes` (default 30); a battery under 10 % alerts once and re-arms above 25 %.
Each has a recovery message where it makes sense, undelivered alerts are retried, and delivery uses the same phone push as network alerts. No model and no writes are involved.
