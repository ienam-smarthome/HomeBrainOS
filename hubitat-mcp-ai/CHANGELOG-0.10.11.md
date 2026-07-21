# 0.10.11

- Follow-on controls now resolve pronouns through verified session device IDs.
- An immediately preceding verified light group remains the target of `turn it off`.
- Failed device writes can no longer be reported as successful because a later
  device search or inventory read succeeded.
