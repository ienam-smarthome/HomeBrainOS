# 0.10.13

- Hub restart requests now create a real pending confirmation scoped to the browser
  session.
- A separate `Yes` calls `hub_reboot` once with `confirm=true`; `No` sends nothing.
- Restart failures and uncertain connection-loss outcomes are reported without an
  unsafe automatic retry.
