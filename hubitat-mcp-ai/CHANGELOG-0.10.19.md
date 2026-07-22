# 0.10.19

- Uses `hub_get_device` for authoritative details after discovering each Octopus
  meter, including transparent category-gateway translation.
- Merges per-device values into compact inventory records with empty states.
- Retains compatibility with older true `hub_read_devices` detail operations.
