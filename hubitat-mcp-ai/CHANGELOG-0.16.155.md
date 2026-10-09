# 0.16.155

Room health failures are now normalized in the deterministic data path before model synthesis.

- Compact live context explicitly includes sensorStatus, healthStatus, mqttStatus, lastMessage and lastError.
- Room evidence preserves those fields and emits a normalized health warning when Hubitat reports offline/unavailable/connectivity failure.
- A health warning marks both retained activity and environmental values unreliable for current-state classification, preventing offline motion=inactive/presence=not present/lux values from being presented as healthy current readings.
- Exact regression coverage reproduces Seeed Studio MR60BHA2 MQTT device 7304: switch on, motion inactive, presence not present, 8.7 lux, sensorStatus offline, mqttStatus connecting, lastMessage offline, and MQTT connect failed: MqttException.
- Conflicting transport evidence is preserved rather than resolved into an invented root cause.

Read-only; no device-control or confirmation behavior changes. Continues #758.
