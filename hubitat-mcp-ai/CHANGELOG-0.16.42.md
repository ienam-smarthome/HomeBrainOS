# Hubitat MCP AI 0.16.42

## Add configured external-automation topology to causal answers

Live Hallway testing proved a useful distinction that Hubitat event history alone
cannot express: some motion automations are owned by an upstream platform such as
Aqara M3 or SmartThings. In those cases Hubitat may only see the sensor reports and
the resulting light state, so the previous deterministic answer could do no better
than "an automation or action outside Hubitat remains possible."

0.16.42 adds an explicit, user-configured topology layer for those external routes.

### What changed

- New `causal_known_automations_json` add-on option describes external automation
  name, platform, trigger devices, and target ON/OFF actions.
- Causal secondary analysis matches only the requested subject/transition and the
  live requested-boundary sensor evidence against that configuration.
- A trigger reported before/effectively with the subject transition is labelled
  timing-consistent with the configured upstream route.
- A trigger reported after the subject transition remains a concrete configured
  candidate, but HomeBrain explicitly says Hubitat's received event order cannot
  prove that run.
- Configured topology never overrides a direct Hubitat command producer and never
  becomes execution provenance by itself.
- Technical metrics add `causal_known_automation_match`.
- The deterministic answer names the known external route instead of ending with
  the generic "outside Hubitat remains possible" conclusion when a configured
  route matches.

### Hallway deployment mapping

This deployment includes the confirmed Aqara M3 automation:

- **Automation:** `Hallway Lights ON`
- **Trigger mode:** any
- **Triggers:** Hallway FP300 / Hallway Aqara P1
- **Actions:** Hallway Light 1 ON / Hallway Light 2 ON

The Hubitat label `Hallway FP300 sensor` is retained as an alias for the Aqara
`Hallway FP300` trigger.

Other deployments can clear, replace, or extend the JSON option. SmartThings-owned
automations use the same schema by setting `platform` to `SmartThings`.

### Safety boundary

This feature deliberately distinguishes three evidence classes:

1. a direct Hubitat command producer is execution provenance and remains strongest;
2. a configured external automation plus matching live timing is concrete topology
   correlation;
3. timing correlation alone remains weaker and cannot name a specific automation.

Even with a topology match, HomeBrain says that Hubitat cannot prove the external
platform executed that exact automation run.

### Expected Hallway proof

For a Hallway Light 1 ON transition with matching FP300 evidence, Technical Details
should include a `knownAutomationMatches` entry and the metric:

```text
causal_known_automation_match: 1
```

The main answer should include a **Known automation** bullet naming Aqara M3
`Hallway Lights ON`, while preserving the no-execution-proof caveat.
