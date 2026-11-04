# HomeBrainOS v0.18.405 — evidence-scoped native app class identity

**Why:** A live read-only request to verify whether a named installed
Rule Machine **app instance** was truly the native parent was classified
as `existing_rule_verification`. That contract asks for action trees,
trigger conditions, rule health and duplicate rule names. Because those
facts were absent, a host finalization guard replaced the model answer
with an irrelevant generic partial-action-tree/lockout-controller checklist.

## Generalized read-only correction

- Explicit app-instance, native/built-in **class**, `appTypeId`,
  type namespace and parent-identity questions are now a distinct
  `app_class_identity` investigation objective. A request for an
  actual installed rule's ordered actions and executable triggers
  still retains the existing strict rule-verification contract.
- Correct advisory model classifications that wrongly turn
  native-class identity into executable-rule certification;
  source scope is chosen from the user's requested deliverable,
  not a model-derived assertion or arbitrary app ID.
- A dedicated evidence contract requires typed app-instance identity
  **and a source-attested instance→appTypeId→native-class relationship**.
  Generic successful `hub_get_app_config`, `hub_list_apps`
  or `hub_get_rule_health` field-name receipts mark sources
  **checked**, not the native parent verified. A partial
  built-in type catalog cannot prove the class does not exist.
- Shared completion discards stale mismatched rule-logic requirement
  sets, preserves the relevant model-authored answer and
  reports unverified class identity under Technical details.
  The existing-rule publication guard has a backstop that
  cannot replace an app-identity answer with action-tree
  / inactivity-OFF boilerplate.
- No additional MCP/model calls, automatic writes, or broader
  permission changes. Nonclass existing Rule Machine audits
  retain their source requirements.

**Safety boundary:** This version does **not** solve the Hubitat
native parent type identity if the MCP server does not provide
an authoritative typed mapping. It prevents irrelevant
classifications and unsupported certification; no rule
writer is unlocked. Any native class claim still requires
verified Hubitat source identity and explicit user permission
for separate future writes.

**Baseline that motivated this generalized fix:** User-provided
read-only HomeBrainOS v0.18.404 response for an installed app
parent-class identity question, **33.825s**, **7 Gemma rounds**,
**4 read-only MCP calls**, unresolved. Its existing-rule
guard message was materially off-topic. The recorded MCP
receipts were only field-name summaries, not source-attested
native class relationships. This is **pre-update evidence**,
not a measured v0.18.405 improvement.

**Acceptance pending installed live test:** Ask the same
read-only native parent class question, provide complete
answer and diagnostic JSON, compare answer relevance,
class verification bounds, number of model rounds, tool
calls and end-to-end latency. No claimed quality uplift,
Claude parity or v0.18.405 latency is established by CI.
