# Colibri local inference pilot — 19 November 2026

**Status:** Optional offline/local experiment, NOT a HomeBrainOS provider change. No V1, V2 alpha.153, native MCP, live authorisation, approval, model-routing or private prospective cohort changes. The probe does not contact Hubitat or Home Assistant and never executes model-requested tools.

## Why this is an experiment

The GMKtec M6 Ultra typically has Ryzen 5 7640HS and integrated Radeon 760M graphics; installed RAM/SSD must be measured locally. Colibri uses RAM, GPU and NVMe tiers to run Mixture-of-Experts models. The project distinguishes loading a large model from useful conversational speed.

Upstream model catalog on 19 November 2026:
- Qwen3.6-35B-A3B (model ID qwen36-35b): about 23 GB download; 10 GB minimum RAM, 20 GB preferred; reasoning and tool calls.
- Qwen3-Coder-30B-A3B (model ID qwen3-coder-30b): about 19 GB download; 8 GB minimum RAM, 18 GB preferred; coding and tool calls.
- GLM-5.2 744B: about 429 GB download and author-reported 0.05–0.1 tokens/s cold on an unrelated 25GB-RAM development laptop. Not recommended as a real-time model here.
- Laya is a separately hosted decision engine (/v1/systemone), not a natural-language answer generator or independent Hubitat permission authority.

## Stage A — local Windows hardware inspection, before model download

Download the official source from https://github.com/JustVugg/colibri using Code > Download ZIP and extract it. From PowerShell within the **upstream Colibri checkout**, run:

    py -3 --version
    py -3 c\setup_hw.py --json
    py -3 c\coli setup --list --json

These inspect the actual system and enumerate models; they do not authorise a download. Compare detected free RAM, disk, GPU backend support and model recommendation. On Windows, the official START-HERE.bat is the guided installer. Only after reading the selected model size and destination, an alternative interactive setup is:

    py -3 c\coli setup --model qwen36-35b --backend auto --no-start

This step will download model files after the user consents. Do not add --yes before checking requirements. WSL users should keep streaming model files on the Linux filesystem, not /mnt/c. An integrated GPU may use Vulkan on supported engines, but CPU versus Vulkan speed must be measured.

## Stage B — run the independent protocol probe

From the **upstream Colibri checkout** on that same Windows PC:

    py -3 c\coli start --background --no-browser
    py -3 c\coli status --json

Use the exact server.model_id and server.urls.openai_base_url reported by status. From a **HomeBrainOS repository checkout** on the same Windows PC, run:

    py -3 scripts\colibri_pilot_probe.py --base-url http://127.0.0.1:8000/v1 --model MODEL_ID

Replace MODEL_ID and, if necessary, the port using status. If configured, COLI_API_KEY is read from the local environment, not from CLI arguments.

The probe performs:
1. Model discovery through GET /v1/models.
2. A short fictional chat completion.
3. A structured tool-call test for a synthetic get_demo_switch(DEMO-ONLY) function.
4. A simulated tool-result continuation with fictional state OFF. The function is **never actually executed**.

It reports request elapsed times, chat_ok, tool_call_ok and tool_roundtrip_ok. Exit 0 = protocol checks passed, 2 = incomplete compatibility, 1 = transport/configuration error. A pass proves neither factual grounding, robust device control, nor production latency. Unit tests are fully mocked:

    py -3 -m unittest tests.test_colibri_local_pilot -v

When finished, from the **upstream Colibri checkout**:

    py -3 c\coli stop

## Safety and acceptance gates

- Keep the initial Colibri server bound to 127.0.0.1. Home Assistant runs on another host, so 127.0.0.1 in the add-on cannot reach the Windows PC. A future private LAN API requires a deliberately bound private IP, authentication, a firewall restricted to the HA host and no internet port-forward.
- The pilot uses fictional text only, never private source receipts or live MCP credentials.
- Evaluate a new local provider only against a newly defined, frozen, **read-only**, source-real HomeBrainOS cohort after this basic protocol pass. Score grounded claims, source completeness, usefulness, causal calibration and p50/p95 latency. Synthetic unit tests cannot establish answer quality.
- Preserve the original alpha.153 acceptance cohort and write-approval gates. No automatic cloud fallback or provider change is implemented here.
- Only consider Laya decision scoring as a future non-authoritative advisory component, not a shortcut around source evidence or the native write gate.

Sources: https://github.com/JustVugg/colibri ; https://github.com/JustVugg/colibri/blob/main/docs/AI_SETUP.md ; https://github.com/JustVugg/colibri/blob/main/docs/api.md ; ../AGENTS.md
