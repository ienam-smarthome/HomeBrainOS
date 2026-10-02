# Hubitat MCP AI 0.16.89

## Internet access switch semantics

This release gives Hubitat devices assigned to the authoritative `Internet` room/group an explicit user-facing access meaning without changing their underlying switch behavior.

### Allowed vs blocked

For devices in the `Internet` group:

- `switch=on` means **Internet allowed**;
- `switch=off` means **Internet blocked**.

HomeBrain is instructed to present these states as `Internet allowed` / `Internet blocked` instead of implying that an ON `Block ...` switch means blocking is active.

### Group-grounded, not name-grounded

The semantic mapping comes from authoritative Hubitat room/group membership. A device merely beginning with `Block` outside the `Internet` group keeps ordinary switch semantics, while an Internet-group device does not need a `Block` prefix to receive the access meaning.

### Command behavior unchanged

The literal Hubitat `switch` state and existing on/off commands are preserved. This release changes presentation semantics only; it does not invert commands, mutate devices during reads, or change the underlying internet-control implementation.

### Home-summary compatibility

Active Internet controls retain `switch=on` in the deterministic switch snapshot for backward compatibility and now also carry:

- `semantic_role=internet_access_control`;
- `internet_access=allowed`; and
- `state_label=Internet allowed`.

This lets the existing home-summary synthesis distinguish access state from an ordinary non-light switch without another Hubitat read or model round.

### Regression coverage

The release gate proves:

- Internet-room ON maps to allowed;
- Internet-room OFF maps to blocked;
- label prefix alone cannot create Internet-control semantics;
- Internet room membership works without a `Block` prefix;
- active switch rows retain the literal state while adding semantic metadata; and
- synthesis policy preserves the underlying on/off command meaning.
