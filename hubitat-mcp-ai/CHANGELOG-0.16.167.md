# 0.16.167 — Verify Rule Machine parent–child health from native details

- Fix regression in the 0.16.166 direct Rule Machine analysis route: `hub_get_device` defaults to a summary without `parentDeviceId`, so it could verify parent 7334 separately yet leave dependent FP2 lux/motion values presented as reported now.
- For each configured sensor, use one authoritative `hub_get_device` read in `mode=details` with `sections=[attributes, relationships]`, and project the nested `sections.relationships.device.parentDeviceId` and `sections.attributes.currentStates` into canonical sensor metadata.
- Use the returned parent IDs to perform bounded numeric `hub_get_device` health checks, with no parent guessed from labels and no historical status inferred.
- When parent is confirmed offline, mark corresponding children as **Parent offline** and their attributes as **last reported, freshness unverified**. A missing relationship produces an evidence-coverage warning and no false association.
- Treat verified offline sensor/parent observations as complete *current* health evidence, while still explicitly not claiming historical condition evaluation.
- Add a privacy-safe `rule_analysis_partial` counter and map incomplete rule investigations to an **unresolved** request outcome (warning rather than unqualified green success). A successfully completed bounded investigation retains success while historical cause remains separately unverified.
- Regression tests now use actual native detailed response sections (cached identities deliberately omit `parentDeviceId`) and check offline inheritance, unreadable parents, absent relationships, and partial-outcome metrics.

Read-only. No Rule Machine app or device state is modified. Existing lighting command attribution stays unchanged.