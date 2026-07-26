# 0.10.136

## Safe shortened Rule Machine matching

- Finds likely Rule Machine candidates from shortened names such as `fridge freezer rule`.
- Ignores filler words including `rule`, `automation`, `the` and `and` when ranking candidates.
- Keeps exact Rule ID confirmation mandatory before any rule write.
- Avoids unsafe broad one-word matches.
- Adds regression coverage for the reported fridge/freezer rule name.
