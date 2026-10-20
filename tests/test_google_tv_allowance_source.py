"""Source-only safety and specification checks for a standalone Hubitat Groovy app.

These tests do NOT execute Groovy or prove live Hubitat behavior. They verify
the repository artifact's safety contract and a small reference state model;
a Hubitat test-install is required before production activation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SRC = (
    Path(__file__).resolve().parents[1]
    / "hubitat-apps"
    / "google-tv-cumulative-allowance.groovy"
)
TEXT = SRC.read_text(encoding="utf-8")


def method_body(name: str) -> str:
    start = TEXT.index(name)
    following = TEXT.find("\ndef ", start + len(name))
    return TEXT[start:following if following >= 0 else len(TEXT)]


def test_safety_guards_default_disabled_exact_ids_and_conflict_acknowledgment():
    assert "defaultValue: false" in TEXT
    assert 'tvPlug.id.toString() == "4221"' in TEXT
    assert 'internetControl.id.toString() == "6923"' in TEXT
    assert 'settings.enableController == true' in TEXT
    assert 'settings.conflictReviewed == true' in TEXT
    assert "private boolean enforcementEnabled()" in TEXT
    assert "if (!enforcementEnabled())" in TEXT
    assert "existing rule 3985" in TEXT.lower()


def test_one_way_control_no_implicit_unblock_or_rule_changes():
    assert TEXT.count("internetControl.off()") == 1
    assert "internetControl.on()" not in TEXT
    assert "internetControl.allowInternet(" not in TEXT
    assert "hub_set_rule" not in TEXT
    assert "hub_manage_rule_machine" not in TEXT
    assert "tvPlug.off()" not in TEXT
    assert "tvPlug.on()" not in TEXT
    assert "runIn(10, \"verifyBlock\"" in TEXT
    assert "NOT verified after three attempts" in TEXT


def test_persistent_usage_and_restart_handling_are_explicit():
    assert "atomicState.usedMs" in TEXT
    assert "atomicState.activeSinceMs" in TEXT
    assert "def initialize()" in TEXT
    assert 'String previousInternet = (atomicState.internetState ?: "").toString()' in TEXT
    assert 'previousInternet == "off" && internetNow == "on"' in TEXT
    assert "atomicState.activeSinceMs = null" in TEXT
    assert "runIn(seconds, \"usageTick\"" in TEXT
    assert 'unschedule("usageTick")' in TEXT
    assert "if (elapsed > 120000L)" in TEXT
    assert "Math.min(budgetMs(), usedMs() + elapsed)" in TEXT


def test_unblocking_is_transition_based_not_a_duplicate_on_read():
    body = method_body("def internetSwitchChanged(evt)")
    assert 'previous == "off" && incoming == "on"' in body
    assert 'resetAllowance(timestamp, "Internet off to on")' in body
    assert "atomicState.awaitingUnblock = true" in body
    assert "atomicState.internetState = incoming" in body
    assert 'unschedule("verifyBlock")' in body


def test_no_automatic_daily_reset_and_an_explicit_counter_only_reset_button():
    assert "midnightReset" not in TEXT
    assert "schedule(" not in TEXT
    assert "def appButtonHandler(String buttonName)" in TEXT
    assert "if (buttonName != \"resetCounter\" || !validDevices()) return" in TEXT
    assert "Internet remains unchanged" in TEXT


@dataclass
class SpecificationModel:
    """Reference semantics only; NOT an interpreter for the Groovy app."""

    used: int = 0
    active: bool = False
    internet_allowed: bool = True
    blocked: bool = False
    allowance: int = 3600

    def tv(self, on: bool) -> None:
        self.active = on

    def elapse(self, seconds: int) -> None:
        if self.active and self.internet_allowed and not self.blocked:
            self.used = min(self.allowance, self.used + seconds)
            if self.used == self.allowance:
                self.internet_allowed = False
                self.blocked = True

    def restore_internet(self) -> None:
        if not self.internet_allowed:
            self.internet_allowed = True
            self.blocked = False
            self.used = 0


def test_specification_cumulative_across_separate_sessions():
    model = SpecificationModel()
    model.tv(True)
    model.elapse(20 * 60)
    model.tv(False)
    model.elapse(60 * 60)
    assert model.used == 20 * 60
    model.tv(True)
    model.elapse(25 * 60)
    model.elapse(15 * 60)
    assert model.used == 3600
    assert model.blocked is True


def test_specification_restoration_gives_fresh_hour_without_turning_tv_off():
    model = SpecificationModel(active=True)
    model.elapse(3600)
    assert model.blocked
    model.restore_internet()
    assert model.used == 0 and model.active and model.internet_allowed
    model.elapse(3599)
    assert not model.blocked
    model.elapse(1)
    assert model.blocked


def test_specification_no_reset_from_tv_off_on_or_clock_time():
    model = SpecificationModel(active=True)
    model.elapse(3500)
    model.tv(False)
    model.tv(True)
    assert model.used == 3500
    model.elapse(100)
    assert model.blocked
