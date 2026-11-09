# HomeBrainOS v2 alpha.21 — private phone-accessible AI benchmark

**Scope:** A separate, user-initiated, tool-free **frozen evidence** evaluation.
The native Hubitat MCP agent, device commands, external recorder and earlier
offline evaluation scripts are unchanged. No benchmark calls a Hubitat tool.

## Phone workflow in Home Assistant ingress

1. Update **Hubitat MCP AI v2** to **2.0.0-alpha.21**, then restart it. The
   UI header and API status must both indicate the same version. Its regular
   Ask/Chat and Hub Diagnostics tabs continue to work as before.
2. Open the v2 add-on in a phone browser, then tap **AI Benchmark**.
3. Download the **previously prepared private** A/B benchmark ZIP from the
   earlier ChatGPT conversation to the phone's Files/Downloads folder.
   **Do not upload this ZIP to GitHub, public drives, or CI.**
4. Use **Choose file → Import ZIP** on the AI Benchmark tab. The page validates
   the manifest, the two conditions and the exact source hashes. The
   private source is stored under the add-on's persistent
   \`/data/homebrain-v2-benchmark/\` directory. Importing never contacts
   Ollama or any Hubitat server.
5. Pick one case or two smaller cases for a pilot. The **Run selected A/B
   pairs** action remains unavailable until the dataset is imported and you
   check both private evidence and cloud/remote transfer acknowledgements.
   The page uses the **existing configured model** from v2 add-on settings.
   For \`gemma4:31b-cloud\` on \`https://ollama.com\`, this requires an
   existing, working Ollama Cloud API key. The benchmark may use paid credits
   and forwards raw private MCP evidence to that model provider. No other
   model is silently substituted. Check your privacy/credit preferences
   before authorising the run.
6. Each selected case produces two separate responses in a
   **retrospective no-tools conversation**, using identical recorded
   questions, system instructions and frozen source receipts. One randomly
   blinded condition has general source-role notes; the other does not.
   Both conditions use the same configured model, temperature 0 and
   seed 42. The HTTP payload intentionally contains **no \`tools\` key**.
   The model **cannot call native MCP** via this evaluator.
7. The interface shows progress and supports **Stop run**. A stopped or
   failed run retains completed answers; you can select the same cases to
   finish missing responses without re-sending completed answers. A
   restarted add-on retains saved imports and completed answers.
8. Choose a case under **Blind review**. Compare A and B with the collapsible
   **original MCP source receipts** (annotations stripped). Score five
   criteria separately for each answer on a 0/1/2 scale, or \`n/a\`:
   \`factual_grounding\`, \`source_completeness\`, \`causal_calibration\`,
   \`command_outcome\`, \`usefulness\`. The A/B mapping is never disclosed
   in the UI before or during scoring.
9. Choose **Generate report** and **Download report JSON**. It contains only
   paired aggregate better/tie/worse counts, differences in scores and model
   elapsed times, and missing-answer/rating counts. No raw questions,
   device IDs, model answers, source receipts, API key, or A/B case mapping.
   A report before both pairs are graded is **pending**, never a success rate.
10. After saving the report, use **Private data controls → Delete all
    benchmark data**. This securely removes local directory entries, not
    remote copies the model provider may already have processed or retained.

## Security and validation boundaries

- ZIP body limit 8 MiB; total declared uncompressed 24 MiB; at most 20 pairs,
  with per-file limits. Reject traversal, symlinks, unexpected files, duplicate
  entries, encrypted ZIPs, missing cases and inconsistent SHA-256. The prepared
  historical ZIP from the user is ~110 KiB compressed and well within limits.
- Files are private, stored under the Home Assistant add-on's \`/data\`
  directory with mode 0700 (directories) and 0600 (files) on POSIX.
  **Anyone with permission to use this add-on's ingress can potentially access
  the private benchmark data.** Consider Home Assistant account access and
  backups before uploading.
- Import/upload, run/stop, source reads, scoring, report and delete all require
  the app's custom same-origin UI request header. No public asset or API
  forwards the user's private sources to GitHub.
- Model requests use the add-on's configured, credentialed Ollama client
  directly with messages and **no native MCP, model-tool definitions,
  permission writer, device action, or tool gateway**. Explicit per-run
  consent is required, including separate cloud/remote transfer consent.
- Untrusted model text is displayed as **textContent** rather than executable
  HTML, including markup embedded in model responses and source receipts.
- The benchmark is a **fixed-source interpretation test**, not live autonomous
  tool selection, model tool-choice performance, physical actuation or proof of
  model improvement. Human blind scoring is essential. For generalisation,
  compare multiple independent device/problem domains and account for
  latency and provider context differences.
- An explicit reset removes the local benchmark dataset. There is no
  automatic download of the household's private evidence, no automatic
  benchmark startup, no scheduled cloud request and no default cloud run.

## Rollback

Install alpha.20 or revert the UI/API/backend/test/docs changes. Private
benchmark files remain in persistent \`/data\` until explicitly deleted; clear
them from alpha.21 before rollback if you want them removed. No changes to
Hubitat, Home Assistant core, native MCP server, Hub Diagnostics, or v1.
