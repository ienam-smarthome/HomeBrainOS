# Hubitat MCP AI 0.16.95

## Explicit Internet-control aliases

- Adds `internet_control_aliases_json`, an empty-by-default JSON object mapping user phrases to exact Hubitat control-surface labels.
- Configured aliases may extend scheduled Internet control beyond devices assigned to the `Internet` room without introducing a global name-prefix heuristic.
- Alias matching is exact after HomeBrain name normalization; the configured target label must identify exactly one current Hubitat device.
- The selected target is still re-read and verified for the real Switch `off`/`on` command before any Rule Machine write is proposed.
- Existing Internet-room semantics remain unchanged: `off` means blocked and `on` means allowed.
- Ordinary device power scheduling remains outside this alias map.

Example:

```yaml
internet_control_aliases_json: '{"Google TV":"Block Media-Google-TV-Streamer"}'
```
