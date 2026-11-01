"""Q1 dashboard declutter without losing legacy diagnostic contracts."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from webui import render_page


class _CardTree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parents = []
        self.entries = {}

    def handle_starttag(self, tag, attrs):
        options = dict(attrs)
        item_id = options.get("id")
        if item_id:
            self.entries[item_id] = {
                "tag": tag,
                "ancestors": tuple(self.parents),
                "open": "open" in options,
            }
        if tag == "details":
            self.parents.append(item_id or "")

    def handle_endtag(self, tag):
        if tag == "details":
            assert self.parents, "unexpected closing details tag"
            self.parents.pop()


def test_old_experiments_are_nested_and_closed_without_removing_controls():
    page = render_page("HomeBrain", "0.18.331")
    tree = _CardTree()
    tree.feed(page)

    assert not tree.parents
    outer = tree.entries["advancedDiagnosticsCard"]
    legacy = tree.entries["legacyCloudExperimentsCard"]
    assert outer["tag"] == "details"
    assert outer["open"] is False
    assert legacy["ancestors"][-1] == "advancedDiagnosticsCard"
    assert legacy["open"] is False

    for item in ("cloudBenchmarkCard", "stage5Card", "stage6Card"):
        assert tree.entries[item]["ancestors"][-2:] == (
            "advancedDiagnosticsCard", "legacyCloudExperimentsCard"
        )
        assert tree.entries[item]["open"] is False

    assert tree.entries["liveShadowCard"]["ancestors"][-1] == "advancedDiagnosticsCard"
    assert "legacyCloudExperimentsCard" not in (
        tree.entries["liveShadowCard"]["ancestors"]
    )
    assert "advancedDiagnosticsCard" not in tree.entries["systemHealthCard"]["ancestors"]
    assert "advancedDiagnosticsCard" not in tree.entries["journalCard"]["ancestors"]

    for control in (
        "runCloudBenchmark", "cloudBenchmarkConsent",
        "runStage5", "stage5Consent",
        "runStage6", "stage6Consent",
        "runLiveShadow", "liveShadowConsent",
        "runLiveShadowHistory", "liveShadowHistoryConsent",
        "runLiveShadowCommands", "liveShadowCommandConsent",
        "runLiveShadowAppDecision", "liveShadowAppConsent",
        "runHealthAudit", "sendPushoverReport",
        "copyLiveShadowAppResult", "copyLiveShadowCommandResult",
        "checkCloudConnection",
    ):
        assert f'id="{control}"' in page


def test_answer_quality_navigation_does_not_invent_benchmark_results():
    page = render_page("HomeBrain", "0.18.331")
    assert "Advanced testing &amp; diagnostics" in page
    assert "Answer Quality is now evaluated against reviewed HomeBrain answers" in page
    assert "Cloud experiments may use your Ollama allowance" in page
    assert "Ollama Cloud benchmark" in page
    assert "Stage 5 · Independent AI investigation" in page
    assert "Stage 6 · Conflicting evidence" in page
    assert "Live Shadow · Read-only preflight" in page
    assert "A fresh local-journal consent is required." in page
    assert "No benchmark run this session." in page
    assert "System check" in page
