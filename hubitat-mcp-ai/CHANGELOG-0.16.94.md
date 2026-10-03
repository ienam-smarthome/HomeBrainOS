# Hubitat MCP AI 0.16.94

## Scheduled Internet access uses real switch semantics

- Aligns RuleAuthoringService with the established Internet-room semantic contract: Hubitat `switch=off` means Internet blocked and `switch=on` means Internet allowed.
- Scheduled `block`/`allow` requests no longer require synthetic `blockInternet`/`allowInternet` device commands.
- Semantic Internet targets are first resolved only among devices assigned to the authoritative Hubitat `Internet` room/group, preventing a similarly named normal device such as `Google TV Streamer (ADB)` from winning the request.
- After the Internet control surface is selected, HomeBrain re-reads it by authoritative label and verifies the real `off` or `on` command before proposing a Rule Machine write.
- `block Google TV after 1 minute` therefore targets `Block Media-Google-TV-Streamer` and schedules `off`; `allow internet for Google TV after 1 minute` schedules `on`.
- Ordinary power scheduling such as `turn off Google TV after 1 minute` is unchanged and remains eligible to target the normal TV/ADB device.
- The Internet-group identity lookup prefers the established enriched `get_cached_devices()` interface and falls back to `get_device_identities()` when needed, preserving compatibility with existing MCP clients while keeping room membership authoritative.
- Relative-delay, absolute-time, recurring Rule Machine grammar, one-time self-pause safety, and confirmation behavior are otherwise unchanged.

## Regression coverage

- Models the real collision between `Google TV Streamer (ADB)` and `Block Media-Google-TV-Streamer` (device 6923).
- The Internet control fixture exposes only ordinary `on`/`off` commands.
- Block scheduling resolves device 6923 and emits Rule Machine `command=off`.
- Allow scheduling resolves device 6923 and emits Rule Machine `command=on`.
- Legacy rule-authoring fixtures now use the authoritative `Internet` room plus real `on`/`off` switch commands rather than synthetic Internet commands.
- The deterministic Internet-room scoping step is evidence-recorded.
