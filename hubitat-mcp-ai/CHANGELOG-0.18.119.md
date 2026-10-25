# HomeBrainOS 0.18.119

This release corrects an unsupported causal attribution from a long-running `motionHandler` warning to later observed lighting delays.

The 0.18.118 response reported a 129,544ms warning at 16:18:42.628 and later OFF commands at 16:58:58.691 and 17:01:16.922. The corresponding last observed, subscribed motion-inactive events occurred 30.058s and 30.269s before the commands. Device state changed OFF within a quarter of a second after each command.

A new typed event guard preserves those measured observations and reports the logged performance anomaly separately instead of claiming it caused the later ON duration. It does not infer physical occupancy, configured timer values, or an ON initiator from a later `setLevel` command. It only activates for app-matched, listener-linked, consistent OFF sequences when the model confidently blames performance latency.

The native WARN parser now recognizes Hubitat `method ... of child app ... ran for ...ms` messages, in addition to ordinary app warnings. Regression tests use the recorded timings and cover missing listeners, unrelated apps, unequal gaps, an alternative app ID, and final API presentation. Hubitat itself remains unchanged.
