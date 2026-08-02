# Live deployment soak testing

Use `scripts/run_live_soak.py` after installing or upgrading the HomeBrain add-on.
The harness is intentionally non-destructive: the sensitive case only verifies
that a structured action is queued for confirmation; it does not send `yes` or
execute the pending mutation.

## Run

Through a directly reachable protected endpoint:

```powershell
python scripts/run_live_soak.py "https://homebrain.example.net"
```

With a bearer-protected reverse proxy:

```powershell
python scripts/run_live_soak.py `
  "https://homebrain.example.net" `
  --token "$env:HOMEBRAIN_TOKEN"
```

Skip the confirmation proposal when no disposable test rule exists:

```powershell
python scripts/run_live_soak.py "https://homebrain.example.net" --skip-confirmation
```

## Covered contracts

The default matrix verifies:

1. A live-state light query returns a message and authoritative evidence.
2. A device-history question returns bounded evidence rather than inferred causation.
3. A log question is grounded in a real diagnostics receipt.
4. A sensitive automation request stops at the confirmation boundary.
5. Every `/api/ask` response exposes the nested `metrics` contract with a valid
   outcome, counter map, and timing map.
6. Every response exposes privacy-safe `metric_rows` using only the stable
   `label` and `value` schema.
7. Metrics and rows do not expose known sensitive key classes such as prompts,
   session identifiers, tool arguments, or device names.

The metrics checks validate the deployed serialization path, not just the Python
presenter in isolation. A response that omits metrics, uses an unknown outcome,
changes the row schema, or exposes a forbidden key fails the soak run.

Each case uses a separate session ID to avoid confirmation or conversation state
leaking between tests. The command exits with status `1` if any contract fails,
so the result can be saved with release evidence or used from a controlled CI
runner that can reach the local Home Assistant instance.

## Manual cancellation checks

Cancellation and browser-disconnect behaviour cannot be proven reliably by a
single portable HTTP script because ingress proxies differ. After the automated
matrix passes, perform these two manual checks:

1. Submit a deliberately slow request, then immediately submit a second request
   in the same browser session. Confirm the first request is superseded and the
   second completes normally.
2. Start a slow request, close or navigate away from the page, then inspect the
   add-on logs. Confirm the backend request is cancelled and no mutation is
   replayed.

Record the installed add-on version, test date, model, pass count, and any failed
response JSON in the release notes or deployment log.
