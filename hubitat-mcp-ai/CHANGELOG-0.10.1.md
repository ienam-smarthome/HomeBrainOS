# 0.10.1

- Keep explicit combined brightness commands such as “turn on living room light 2
  at 90%” on the deterministic control path, stripping the level syntax from the
  device name and avoiding unnecessary fuzzy device confirmation.
