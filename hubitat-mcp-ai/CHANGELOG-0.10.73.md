# Hubitat MCP AI 0.10.73

- Replaces the invalid empty `hub_read_devices` gateway request in the thermostat
  reader with `hub_list_devices` followed by `hub_get_device`.
- Prioritises the exact device labelled `Thermostat` over bedroom and hallway
  TRVs for an unqualified thermostat setpoint question.
- Adds regression coverage with compact inventory data where temperature is
  present but setpoint attributes are available only from the detailed read.
