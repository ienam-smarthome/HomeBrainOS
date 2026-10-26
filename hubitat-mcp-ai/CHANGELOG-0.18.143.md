# HomeBrainOS v0.18.143 — Remember V2 test access in your browser

The V2 tester previously required repeatedly typing the configured access token.
You can now tick **Remember access on this browser for 30 days** to keep a
revocable, signed browser sign-in cookie instead of saving the raw secret.

- The operator's V2 test token is validated once by the original
  `require_test_access` gate before issuing a HMAC-authenticated, randomised
  `HttpOnly; SameSite=Strict` cookie with 30-day expiry.
- Browser JavaScript cannot read the signed cookie or store the original token
  in localStorage/sessionStorage. The token field is cleared once browser
  access is granted.
- The existing test endpoint accepts the cookie only for explicitly authorised
  read-only POSTs with `X-HomeBrain-V2-Request: read-only` and still enforces
  `explicit_opt_in`. Direct token-header requests continue to work.
- Browser status and **Forget saved access** controls support sign-in and
  sign-out. Changing the configured V2 token, or disabling V2, revokes all old
  browser access. The sign-in is local to each browser, not synced to other
  devices or saved in the model's memory.
- Security: the cookie is a bearer credential, so use HTTPS where possible.
  The UI explicitly warns when Home Assistant ingress runs over local HTTP.
  No separate database or user secrets are introduced.

This release does not modify the V2 semantic engine, production V1, Hubitat
device controls or write-permission checks.
