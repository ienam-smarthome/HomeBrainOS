# HomeBrainOS 0.18.109 — diagnose and bound slow AI-led investigations

## Live failure motivating this release
The first 0.18.108 read-only Livingroom Light 1 reasoning test ended with HTTP 504:
"Investigation exceeded its time limit before verified results were collected."
The former default overall deadline was 90 seconds. The HTTP 504 means no verified
read receipt or completed checkpoint was retained at that deadline; it does
**not** prove which stage was slow, or that the Hubitat MCP server failed.

## Changes
- Default `investigation_deadline_seconds` raised from 90 to 180 for read-only
  investigations. Existing installations may retain the previous saved option;
  set it explicitly to 180 in Home Assistant add-on Configuration before retesting.
- Progress distinguishes AI scope interpretation, numbered AI reasoning rounds,
  and numbered tool-execution rounds.
- On a no-evidence timeout, the 504 reports the last observed phase and suggests
  checking add-on logs and the configured deadline. Server logs record request ID,
  deadline, phase, verified-read count and checkpoint presence, never prompt
  content or credentials.
- Existing safe fallback remains intact: if *successful read-only* receipts were
  recorded, return an incomplete evidence-only result, never invented causal
  conclusions or recommendations.
- No changes to write permissions, model-provider selection, source-verification
  logic or the live Hubitat system.

## Scope and limitations
This is a deadline and diagnostic improvement, not proof of a slow Groovy read.
The new phase information can identify whether future timeouts occur before the
first read, during tool execution, or during AI synthesis. The 180-second limit
is still finite. Slow provider calls or MCP reads may exhaust it; increasing the
limit does not by itself make reasoning more efficient.

## Live check
With `investigation_deadline_seconds: 180`, repeat the 0.18.108 Livingroom
Light 1 read-only question and review the full Technical JSON plus add-on Logs.
Check number of verified reads, actual Groovy source evidence for installed
app 4019, sensor roles, 30-second inactivity and five-minute backup branches.
If still timed out, use the last-phase diagnostic to plan the next optimisation.
