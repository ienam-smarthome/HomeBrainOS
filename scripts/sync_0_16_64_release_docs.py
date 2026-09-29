from pathlib import Path

readme = Path("hubitat-mcp-ai/README.md")
text = readme.read_text(encoding="utf-8")
old = "Current add-on version: **0.16.63**."
new = "Current add-on version: **0.16.64**."
if old in text:
    text = text.replace(old, new, 1)

anchor = "## Architecture\n\n"
release_note = (
    "0.16.64 tightens the broad performance path after the 0.16.63 live proof. "
    "Broad performance requests that also ask for recommendations must attempt one "
    "bounded recent `hub_get_logs` read before finalizing. Scheduler/job lists are "
    "kept separate from CPU/load attribution, assertive `likely caused by` mechanism "
    "wording remains unproven even under a Hypothesis label, `sessionTick`/job interval "
    "tuning is inspection-first without configuration evidence, database size remains "
    "a measured MB value rather than a qualitative performance diagnosis, and network "
    "backup alerts no longer imply imminent data loss without supporting evidence.\n\n"
)
if release_note not in text:
    text = text.replace(anchor, anchor + release_note, 1)
readme.write_text(text, encoding="utf-8")

index = Path("hubitat-mcp-ai/CHANGELOG-INDEX.md")
text = index.read_text(encoding="utf-8")
entry = "- [0.16.64](CHANGELOG-0.16.64.md)\n"
if entry not in text:
    text = text.replace("## Current release\n\n", "## Current release\n\n" + entry, 1)
index.write_text(text, encoding="utf-8")
