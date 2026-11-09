"""Private, tool-free A/B evaluation over user-imported frozen MCP evidence.

This module does not import or call Hubitat MCP, invoke Agent.answer, or
mutate any hub. The user must explicitly approve sharing their raw recorded
evidence with the configured model before each run. Files remain under /data.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import statistics
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx


SCHEMA = "homebrain-v2-fixed-source-pairs.v1"
CATEGORIES = ("factual_grounding", "source_completeness", "causal_calibration",
              "command_outcome", "usefulness")
CASE_RE = re.compile(r"case-\d{3}$")
BUNDLE_RE = re.compile(r"case-\d{3}-[AB]\.json$")
MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_UNPACKED_BYTES = 24 * 1024 * 1024
MAX_BUNDLE_BYTES = 3 * 1024 * 1024
MAX_PAIRS = 20


class BenchmarkError(ValueError):
    """A non-sensitive, safe-to-display validation or workflow error."""


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _clean_receipts(receipts: list) -> list:
    return [{k: v for k, v in call.items() if k != "generic_source_role_note"}
            for call in receipts]


def _private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
        if os.name == "posix":
            os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_bundle(document: Any) -> None:
    if not isinstance(document, dict):
        raise BenchmarkError("Invalid frozen evidence bundle")
    if not (isinstance(document.get("instructions"), str)
            and 0 < len(document["instructions"]) <= 10000
            and isinstance(document.get("recorded_user_question"), str)
            and 0 < len(document["recorded_user_question"]) <= 10000
            and isinstance(document.get("native_tool_receipts"), list)
            and 0 < len(document["native_tool_receipts"]) <= 200):
        raise BenchmarkError("Frozen question or source receipts are invalid")
    if not all(isinstance(c, dict) for c in document["native_tool_receipts"]):
        raise BenchmarkError("Invalid MCP receipt type")


def _validate_zip(blob: bytes) -> tuple[dict, dict, dict[str, dict]]:
    if len(blob) > MAX_ZIP_BYTES:
        raise BenchmarkError("Benchmark ZIP exceeds 8 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_PAIRS * 2 + 3:
                raise BenchmarkError("Too many benchmark files")
            names = [entry.filename for entry in infos]
            if len(names) != len(set(names)) or not names:
                raise BenchmarkError("Duplicate or empty ZIP entries")
            for entry in infos:
                if (entry.is_dir() or entry.filename not in (
                        "private_manifest.json", "blind_ratings.json",
                        "README_PRIVATE.txt") and not BUNDLE_RE.fullmatch(entry.filename)
                        or entry.file_size > MAX_BUNDLE_BYTES
                        or entry.flag_bits & 1
                        or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    raise BenchmarkError("Unsupported ZIP entry")
            if sum(entry.file_size for entry in infos) > MAX_UNPACKED_BYTES:
                raise BenchmarkError("Uncompressed evidence exceeds safe size")
            if "private_manifest.json" not in names or "blind_ratings.json" not in names:
                raise BenchmarkError("Benchmark ZIP is missing its manifest")
            manifest = json.loads(archive.read("private_manifest.json"))
            ratings = json.loads(archive.read("blind_ratings.json"))
            if (not isinstance(manifest, dict)
                    or manifest.get("schema") != SCHEMA
                    or not isinstance(manifest.get("cases"), list)
                    or not 1 <= len(manifest["cases"]) <= MAX_PAIRS):
                raise BenchmarkError("Unsupported benchmark manifest")
            if (not isinstance(ratings, dict) or ratings.get("schema") != SCHEMA
                    or not isinstance(ratings.get("cases"), dict)):
                raise BenchmarkError("Unsupported scoring template")
            pairs = {}
            for item in manifest["cases"]:
                if not isinstance(item, dict):
                    raise BenchmarkError("Invalid case entry")
                key = item.get("case_id")
                mapping = item.get("condition_map")
                digest = item.get("source_sha256")
                if (not isinstance(key, str) or not CASE_RE.fullmatch(key)
                        or key in pairs or not isinstance(mapping, dict)
                        or set(mapping) != {"A", "B"}
                        or set(mapping.values()) != {"baseline", "role_notes"}
                        or not isinstance(digest, str)
                        or not re.fullmatch("[0-9a-f]{64}", digest)):
                    raise BenchmarkError("Invalid benchmark pairing or hash")
                variants = {}
                for label in ("A", "B"):
                    filename = key + "-" + label + ".json"
                    if filename not in names:
                        raise BenchmarkError("A benchmark condition is missing")
                    variants[label] = json.loads(archive.read(filename))
                    _validate_bundle(variants[label])
                a, b = variants["A"], variants["B"]
                if (a["instructions"] != b["instructions"]
                        or a["recorded_user_question"] != b["recorded_user_question"]
                        or _sha(_clean_receipts(a["native_tool_receipts"])) != digest
                        or _sha(_clean_receipts(b["native_tool_receipts"])) != digest):
                    raise BenchmarkError("Paired MCP source integrity mismatch")
                base = variants["A"] if mapping["A"] == "baseline" else variants["B"]
                note = variants["B"] if mapping["A"] == "baseline" else variants["A"]
                if (any("generic_source_role_note" in r for r in base["native_tool_receipts"])
                        or not any("generic_source_role_note" in r
                                   for r in note["native_tool_receipts"])):
                    raise BenchmarkError("The blinded A/B source conditions are invalid")
                pairs[key] = variants
            if {k for k in names if BUNDLE_RE.fullmatch(k)} != {
                    f"{key}-{label}.json" for key in pairs for label in ("A", "B")}:
                raise BenchmarkError("ZIP contains unreferenced benchmark cases")
            if set(ratings["cases"]) != set(pairs):
                raise BenchmarkError("Scoring cases do not match the source manifest")
            return manifest, ratings, pairs
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeError, EOFError,
            OSError, KeyError, TypeError, OverflowError) as exc:
        raise BenchmarkError("Cannot read or verify this private benchmark ZIP") from None


def _valid_score(score: Any) -> bool:
    return score == "n/a" or type(score) is int and score in (0, 1, 2)


class BenchmarkWorkspace:
    def __init__(self, root: Path):
        self.root = Path(root)

    def available(self) -> bool:
        return (self.root / "private_manifest.json").is_file()

    def _manifest(self) -> dict:
        if not self.available():
            raise BenchmarkError("Import your prepared benchmark ZIP first")
        return _load(self.root / "private_manifest.json")

    def _ratings(self) -> dict:
        return _load(self.root / "blind_ratings.json")

    def _bundle(self, key: str, label: str) -> dict:
        return _load(self.root / (key + "-" + label + ".json"))

    def _answer_path(self, key: str, label: str) -> Path:
        return self.root / "answers" / (key + "-" + label + ".txt")

    def _answer(self, key: str, label: str) -> str | None:
        path = self._answer_path(key, label)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def _keys(self) -> list[str]:
        return [c["case_id"] for c in self._manifest()["cases"]]

    def import_zip(self, blob: bytes) -> int:
        if self.available():
            raise BenchmarkError("A private dataset already exists; delete it explicitly before replacing")
        manifest, ratings, pairs = _validate_zip(blob)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.root, 0o700)
        for key, variants in pairs.items():
            for label, bundle in variants.items():
                _private_write(self.root / (key + "-" + label + ".json"),
                               json.dumps(bundle, ensure_ascii=False))
        _private_write(self.root / "blind_ratings.json",
                       json.dumps(ratings, ensure_ascii=False))
        (self.root / "answers").mkdir(mode=0o700, exist_ok=True)
        # Write manifest last so interrupted imports cannot masquerade as ready.
        _private_write(self.root / "private_manifest.json",
                       json.dumps(manifest, ensure_ascii=False))
        return len(pairs)

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def summary(self, running: bool = False, error: str | None = None,
                progress: dict | None = None) -> dict:
        if not self.available():
            return {"imported": False, "running": running, "cases": [], "error": error,
                    "model_calls": 0}
        ratings = self._ratings()["cases"]
        cases = []
        for key in self._keys():
            complete = all(self._answer(key, label) is not None for label in ("A", "B"))
            graded = complete and all(
                _valid_score(ratings[key][label]["ratings"].get(category))
                for label in ("A", "B") for category in CATEGORIES
            )
            cases.append({"id": key, "answered": complete, "graded": graded})
        return {"imported": True, "running": running, "cases": cases,
                "error": error, "progress": progress or {}, "model_calls": 0,
                "scoring_dimensions": list(CATEGORIES)}

    def case(self, key: str) -> dict:
        if key not in self._keys():
            raise BenchmarkError("Unknown benchmark case")
        manifest = self._manifest()
        item = next(c for c in manifest["cases"] if c["case_id"] == key)
        baseline_label = next(label for label in ("A", "B")
                              if item["condition_map"][label] == "baseline")
        source = self._bundle(key, baseline_label)
        a, b = self._answer(key, "A"), self._answer(key, "B")
        # Do not show the assignment or source-role notes to a blinded reviewer.
        return {
            "id": key, "question": source["recorded_user_question"],
            "source": source["native_tool_receipts"],
            "both_answered": a is not None and b is not None,
            "answers": {"A": a, "B": b} if a is not None and b is not None else {},
            "ratings": self._ratings()["cases"][key],
        }

    def pending(self, keys: list[str]) -> list[tuple[str, str]]:
        known = self._keys()
        if not keys or len(keys) > 2 or len(set(keys)) != len(keys) or (
                any(key not in known for key in keys)):
            raise BenchmarkError("Select one or two valid benchmark cases")
        return [(key, label) for key in keys for label in ("A", "B")
                if self._answer(key, label) is None]

    def store_answer(self, key: str, label: str, answer: str, duration_ms: float) -> None:
        if key not in self._keys() or label not in ("A", "B"):
            raise BenchmarkError("Unknown benchmark result")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 250000:
            raise BenchmarkError("Model returned no usable answer")
        if self._answer(key, label) is not None:
            raise BenchmarkError("The answer is already recorded")
        path = self._answer_path(key, label)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(answer)
        ratings = self._ratings()
        ratings["cases"][key][label]["elapsed_ms"] = round(float(duration_ms), 3)
        _private_write(self.root / "blind_ratings.json",
                       json.dumps(ratings, ensure_ascii=False))

    def score(self, key: str, scores: dict) -> None:
        if key not in self._keys() or not all(
                self._answer(key, label) is not None for label in ("A", "B")):
            raise BenchmarkError("Both answers must be completed before scoring")
        if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
            raise BenchmarkError("Score both blind conditions A and B")
        for label in ("A", "B"):
            value = scores[label]
            if (not isinstance(value, dict) or set(value) != set(CATEGORIES)
                    or not all(_valid_score(v) for v in value.values())):
                raise BenchmarkError("Each criterion must be 0, 1, 2 or n/a")
        ratings = self._ratings()
        for label in ("A", "B"):
            ratings["cases"][key][label]["ratings"] = scores[label]
        _private_write(self.root / "blind_ratings.json",
                       json.dumps(ratings, ensure_ascii=False))

    def report(self) -> dict:
        manifest = self._manifest()
        ratings = self._ratings()["cases"]
        changes = {name: [] for name in CATEGORIES}
        times = []
        complete = 0
        answered = 0
        for item in manifest["cases"]:
            key = item["case_id"]
            if self._answer(key, "A") is None or self._answer(key, "B") is None:
                continue
            answered += 1
            records = ratings[key]
            if not all(_valid_score(records[label]["ratings"].get(category))
                       for label in ("A", "B") for category in CATEGORIES):
                continue
            complete += 1
            baseline = records[next(label for label in ("A", "B")
                                    if item["condition_map"][label] == "baseline")]
            note = records[next(label for label in ("A", "B")
                                if item["condition_map"][label] == "role_notes")]
            for name in CATEGORIES:
                b, n = baseline["ratings"][name], note["ratings"][name]
                if b != "n/a" and n != "n/a":
                    changes[name].append(n - b)
            a, b = baseline.get("elapsed_ms"), note.get("elapsed_ms")
            if all(type(x) in (float, int) and math.isfinite(x) and 0 <= x <= 3600000
                   for x in (a, b)):
                times.append(b - a)
        return {
            "schema": "homebrain-v2-fixed-source-report.v1",
            "case_pairs_prepared": len(manifest["cases"]),
            "paired_answers_completed": answered,
            "blind_reviewed_pairs": complete,
            "missing_pair_answers": len(manifest["cases"]) - answered,
            "missing_pair_ratings": answered - complete,
            "condition_effects": {name: {
                "rated_pairs": len(values),
                "mean_role_notes_minus_baseline": (
                    round(statistics.mean(values), 3) if values else None),
                "role_notes_better": sum(v > 0 for v in values),
                "tied": sum(v == 0 for v in values),
                "baseline_better": sum(v < 0 for v in values),
            } for name, values in changes.items()},
            "elapsed_ms_difference_role_notes_minus_baseline": {
                "paired_samples": len(times),
                "median_difference": round(statistics.median(times), 3) if times else None,
            },
            "private_values_exported": False,
            "live_hub_actions_executed": 0,
            "interpretation": "Blind human-rated, frozen source interpretation only; not live autonomous-tool reliability or physical confirmation.",
        }


async def model_answer(model_agent: Any, bundle: dict, timeout: float) -> tuple[str, float]:
    """Use the configured Ollama HTTP client WITHOUT a tools argument."""
    started = time.monotonic()
    try:
        response = await asyncio.wait_for(model_agent.client.post(
            model_agent.base_url + "/api/chat",
            json={
                "model": model_agent.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": bundle["instructions"]},
                    {"role": "user", "content": json.dumps({
                        "recorded_user_question": bundle["recorded_user_question"],
                        "native_tool_receipts": bundle["native_tool_receipts"],
                    }, ensure_ascii=False)},
                ],
                "options": {"temperature": 0, "seed": 42},
            },
        ), timeout=timeout)
        response.raise_for_status()
        data = response.json()
        msg = data.get("message") if isinstance(data, dict) else None
        if not isinstance(msg, dict) or msg.get("tool_calls"):
            raise BenchmarkError("Model returned an invalid or tool-calling response")
        answer = msg.get("content")
        if not isinstance(answer, str) or not answer.strip():
            raise BenchmarkError("Model returned an empty text answer")
        return answer, (time.monotonic() - started) * 1000
    except asyncio.CancelledError:
        raise
    except BenchmarkError:
        raise
    except (httpx.HTTPError, asyncio.TimeoutError, ValueError, KeyError):
        # Never echo remote responses or source payloads into UI/log messages.
        raise BenchmarkError("Model request failed or timed out; check the configured model and credits") from None


async def run_pairs(workspace: BenchmarkWorkspace, agent: Any, keys: list[str],
                    timeout: float, progress: dict) -> None:
    targets = workspace.pending(keys)
    random.Random(42).shuffle(targets)
    progress["total_requests"] = len(targets)
    progress["completed_requests"] = 0
    for key, label in targets:
        bundle = workspace._bundle(key, label)
        text, elapsed = await model_answer(agent, bundle, timeout)
        workspace.store_answer(key, label, text, elapsed)
        progress["completed_requests"] += 1
