# 0.10.9

- Added deterministic named-rule control for pause, resume, enable, disable, run
  and stop commands.
- Exact normalized labels and Rule IDs execute without unnecessary device-choice
  prompts; ambiguous or partial labels remain read-only and request clarification.
- Rule Machine enable/disable is implemented as resume/pause, and stop cancels
  currently running actions without pausing future triggers.
