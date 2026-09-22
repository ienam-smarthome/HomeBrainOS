# Hubitat MCP AI 0.16.5

## Natural read-aloud phrasing

The web UI now normalizes display-oriented symbols before text-to-speech playback.

For example, a visible result such as:

```
Hallway Light 2 50% → 70%
```

is spoken naturally as:

```
Hallway Light 2 50 percent to 70 percent
```

instead of the speech engine announcing the arrow symbol as “right arrow”.

The visual answer remains unchanged; only the spoken form is normalized.

Additional normalization includes:

- `→` → “to”
- `←` → “from”
- numeric percentages such as `50%` → “50 percent”

Regression coverage pins these transformations in the rendered web UI.
