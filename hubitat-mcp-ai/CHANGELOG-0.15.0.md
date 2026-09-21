# Hubitat MCP AI 0.15.0

## Semantic Agent Core

0.15.0 begins the architecture shift from phrase-by-phrase routing to a
meaning-first smart-home agent.

### Typed semantic planning

- Add a strict semantic intermediate representation for:
  - goal/domain
  - target scope/name/kind
  - action
  - timing
  - clarification state
  - confidence
- Add `SemanticPlanner`, which asks the reasoning model to interpret natural
  language only. The planner receives no Hubitat gateway names, device IDs, or
  wire-format instructions.
- Keep trivial exact controls fast: the existing zero-model grammar now converts
  into the same semantic representation instead of representing a separate
  execution architecture.
- Add `SemanticAgentCore`, which compiles an approved semantic plan into the
  deterministic HomeBrain control adapter.

### Intelligent relative brightness

- Add semantic `adjust_level` actions for natural requests such as:
  - "increase living room brightness"
  - "make the living room brighter"
  - "turn the lights up"
  - "dim Bedroom 1"
- Relative changes with no explicit amount use
  `semantic_default_brightness_step` (20 percentage points by default).
- Small/default/large semantic magnitude is mapped to stable policy values rather
  than letting the model invent a different adjustment each turn.
- Relative brightness reads every matched light's authoritative live `level`
  immediately before calculating the new value.
- Clamp every target independently to the 0-100 range.
- Compile the result to deterministic Hubitat `setLevel` calls with positional
  parameter arrays and live `waitFor level` verification.
- Report per-device before/after brightness values.

### Safety and execution boundary

- The semantic model cannot author raw Hubitat commands or payloads.
- Routine semantic control is limited to the existing light/switch adapter.
- Sensitive/admin domains (locks, garages, security, firmware, network blocking,
  rule authoring) remain outside this routine semantic executor and continue
  through their established guarded paths.
- Invalid/unsupported semantic plans fall back to the established agent rather
  than being guessed into an action.

### Goal-state outcomes

- Add an explicit `needs_input` request outcome.
- A genuine clarification is no longer displayed as a green Success merely
  because no known failure counter fired.
- Add privacy-safe semantic counters for AI plans, fast-path plans, relative
  controls, planner/compile failures, and clarification requests.

### Configuration

- `semantic_agent_enabled: true`
- `semantic_default_brightness_step: 20`

### Validation

Regression coverage includes:

- model JSON -> strict semantic plan validation
- paraphrase-broad relative-brightness candidate routing
- zero-tool semantic planner contract
- zero-model fast path -> same semantic IR
- relative brightness live-state reads
- per-device clamping and compilation
- positional `setLevel` payloads and final-level verification
- before/after result presentation
- `needs_input` outcome classification/presentation
- end-to-end semantic control routing without entering the general tool loop
