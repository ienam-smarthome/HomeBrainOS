# 0.18.18 — Free / Paid model selector for each HomeBrain question

## Feature
- Add a compact **AI model** selector to the Home Assistant ingress Ask/Speak card: **Auto · current routing**, **Free · Gemma**, **Paid · DeepSeek Pro**.
- Auto (default after page load) preserves existing HomeBrain manual/hybrid/paid routing behaviour. Auto in hybrid mode may incur paid charges based on existing rules.
- Free explicitly selects the configured default/free model for **this request** and prohibits paid escalation from hybrid rules, natural-language paid phrases and automatic free-quota fallback. If the free quota is unavailable, fail rather than silently charge.
- Paid explicitly requests configured `ollama_paid_deep_model` (DeepSeek Pro) for this request even if the global routing mode is manual. It still obeys the administrator's paid-enabled setting, conservative local spending reservation guard, tool permissions and confirmation requirements.
- Both /api/ask and /api/chat accept optional validated `model_tier: auto | free | paid`. A missing field means Auto to preserve all existing integrations. The answer may report the requested selection separately from the actual model recorded in model round details.
- All UI submit paths (typed, speech, shortcuts and confirmations) use the current choice. Paid is visually disabled if the API reports paid routing disabled. The page defaults to Auto after reload and never saves the choice persistently.
- Use request-scoped context variables rather than global mutable switches, synthetic question prefixes or writing API tokens. Concurrent requests are isolated. The selected tier does not grant any Hubitat command permissions.

## Validation
- Regression tests for free overriding hybrid and paid automatic rules, free tier never charging on provider quota exhaustion even if auto-paid fallback is enabled, paid-only model selection, disabled/zero budget rejection, concurrent request isolation, and strict invalid-value rejection.
- API and web UI contract checks verify the new field, existing response shape and model selection interface.
- No new paid authorization, no raised credit limit, no ledger reset, no changes to device states or automations.

## Live confirmation
After installing, use **Free** for one read-only request and verify all model rounds use Gemma. Then select **Paid** for an independent read-only question with sufficient reserved budget and confirm DeepSeek in `model_round_details` and `paid_routing.used`. Actual Ollama billing remains separate from HomeBrain's conservative reservation estimates.
