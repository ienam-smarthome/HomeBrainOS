# HomeBrainOS v0.18.195 — Nested app evidence and model source-read argument repair

## Observed regression: v0.18.194, 28 October 2026 23:20

The latest native V2 investigation completed in 11.601 seconds with **five successful MCP READs**. It correctly resolved Google Nest Hub (device 7934), retrieved three generic excessive-load WARN rows at 19:55:19, and retrieved 43 device events attesting commands from **Adhan Player (app 1679)** and **00 Google Calendar Notifier (app 4080)**.

The next investigation step failed:
- A successful **hub_get_app_config(appId=1679)** source read returned a settings-page envelope with **nested `app`**, `page.name=settingsPage`, `childApps` and a settings count. The native evidence projector incorrectly looked only for flat `id` / `name` / `settings` and rendered an empty app label/ID/configuration.
- Two model-generated **hub_get_source** calls omitted mandatory **`id` and `type`**. Both were correctly rejected by the host; no source was examined. The second invalid proposal triggered the repeated-invalid guard. That guard reduced cost but did not teach the model how to make a valid follow-up source read.
- The 19:55 generic warnings had no contemporaneous command in this bounded history. Previous slow `setVolume` and `runQ` warnings are a distinct source window; a command issuer is not a proven runtime cause.

## General-purpose improvements

1. **Typed nested app-config projection.** The source adapter recognises `{page:{name},app:{...},childApps:[...],settingsKeyCount}` and retains whitelisted app identity, label, namespace, type, enabled/paused state, form field *names*, settings field counts and child app *IDs*. It also supports older flat app-config responses. **No settings values, secrets, endpoint, HTML or source code are projected.** Resulting app metadata is still a current-state snapshot, not proof of historical execution.
2. **Verified request identity in receipts.** Successful app-config results keep the previously authorised `appId` from the read call, even when a source page omits `app.id`. If the returned app ID disagrees with the requested app ID, the evidence highlights an identity mismatch rather than claiming a verified matching configuration.
3. **Concrete read-only source contract.** On a missing-required-fields rejection, the model sees the exact reviewed `hub_get_source` argument shape: `{type:'app', id:'<attested app ID>'}` or `{type:'driver', id:'<separately attested driver ID>'}`. It receives bounded lists of independently attested app/driver IDs and an explicit statement that the host will not execute the rejected read. Wrong namespace or unverified IDs remain blocked by the pre-existing guards.
4. **Evidence-accurate app summary.** A successfully retrieved, nested settings page is displayed as the requested app's current config metadata, including which fields actually appeared, not an empty "app (ID )" sentence. Source mismatch remains an explicit uncertainty.
5. **General model guidance.** The native READ agent explains `hub_get_app_config` and `hub_get_source` required parameters without keyword routing or auto-inserting arguments.

## Acceptance, safety and limitations

Tests cover nested and flat app responses, secret/PII and endpoint exclusion, mandatory source argument errors, separate app/driver/device ID namespaces, model-driven recovery from one failed source proposal to a valid source metadata read, no raw source code exposure, and mismatched app identity.

This release **does not yet analyse app or driver source code**; it returns bounded source metadata and reports that limitation. It does not establish why the Nest Hub driver executed `runQ` / `setVolume` slowly or why the generic 19:55 excessive-load messages appeared. Source-code control-flow extraction and atomic claim-to-evidence validation remain separate planned stages. The experimental V2 remains strictly READ-only; production Main Ask and Hubitat devices/rules/automations are unchanged.
