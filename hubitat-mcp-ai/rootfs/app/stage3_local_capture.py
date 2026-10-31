"""Stage 3F: explicit, local, in-memory, pseudonymised model-read capture.

No files, network, new MCP calls, prompt recording, real identifier export,
scheduler or background job. This object can *only* be explicitly injected
into an agent constructed with stage3_shadow_mode='observe'. The installed
add-on does not construct or enable it.

Projection preserves read identity equality and exact repeated scopes for
offline Stage 3D/3E comparison. It intentionally does NOT preserve real
timestamps, event values, source chronology, answer text or causal evidence.
A model observation is not independently authenticated provenance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import threading
import time
from typing import Any, Mapping, Sequence

from canonical_investigation_evidence import build_canonical_evidence_view
from stage3_evidence_frontier import (
    _COMMANDS, _READ_SCOPES, _args, _id, _scope,
)
from stage3_loop_shadow import _call_arguments, _declared_operations
from stage3_trace_privacy_report import build_stage3e_private_trace_report

_CONSENT = "AUTHORISE_LOCAL_READ_TRACE"
_MAX_ROUNDS = 12
_MAX_PRIOR_READS = 100
_MAX_NAMES = 20
_MAX_COMMANDS = 20
_MAX_CALLS = 16
_MAX_SCHEMAS = 60
_DOMAINS = frozenset((
    "lighting", "heating", "ventilation", "power", "history",
    "security", "connectivity", "sensors", "media", "other",
))
_GATEWAYS = frozenset(("hub_read_devices", "hub_read_apps_code",
                       "hub_read_rules", "hub_read_diagnostics"))
_ATTRIBUTES = frozenset((
    "switch", "motion", "occupancy", "presence", "level", "temperature",
    "humidity", "power", "energy", "battery", "contact", "illuminance",
    "thermostatMode", "thermostatOperatingState", "heatingSetpoint",
    "coolingSetpoint", "valve", "windowShade", "mode", "lock",
))
_UNBOUND = object()
_SYNTHETIC_START = datetime(2001, 1, 1, tzinfo=timezone.utc)


class LocalStage3FCapture:
    """One explicitly approved, single-request capture with time-boxed RAM.

    `disable()` synchronously drops the per-session key and all retained
    records. Python cannot guarantee zeroisation of reclaimed process memory;
    no claim about forensic memory erasure is made.
    """

    def __init__(
        self, *, consent: str, domain: str = "other",
        ttl_seconds: int = 900, clock: Any = None,
    ) -> None:
        if consent != _CONSENT:
            raise ValueError("explicit local capture consent required")
        if domain not in _DOMAINS:
            raise ValueError("domain must be an allowlisted category")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise ValueError("capture lifetime must be 1 to 900 seconds")
        self._clock = clock if clock is not None else time.monotonic
        self._deadline = float(self._clock()) + ttl_seconds
        self._lock = threading.RLock()
        self._key = secrets.token_bytes(32)
        self._rounds: list[dict[str, Any]] = []
        self._owner: Any = _UNBOUND
        self._domain = domain
        self._enabled = True
        self._skipped = 0

    def _live(self) -> bool:
        if self._enabled and float(self._clock()) >= self._deadline:
            self.disable()
        return self._enabled

    def disable(self) -> None:
        """Immediate logical deletion and revocation; irreversible per object."""
        with self._lock:
            self._enabled = False
            self._rounds.clear()
            self._key = b""
            self._owner = _UNBOUND

    def _pseudonym(self, kind: str, raw: Any) -> str | None:
        ident = _id(raw)
        if not ident:
            return None
        result = hmac.new(self._key, (kind + ":" + ident).encode(),
                          hashlib.sha256).digest()
        # Positive, <=16-digit numeric scope, stable ONLY for this session.
        prefix = 10_000_000_000_000 if kind == "device" else 20_000_000_000_000
        return str(prefix + int.from_bytes(result[:5], "big"))

    def _window(self, start: str, end: str) -> tuple[str, str]:
        # A fake, stable, one-hour interval keyed by *pair* equality. This
        # intentionally destroys actual date, local clock and duration.
        digest = hmac.new(self._key, (start + "\x00" + end).encode(),
                          hashlib.sha256).digest()
        index = int.from_bytes(digest[:3], "big")
        synthetic = _SYNTHETIC_START + timedelta(hours=index)
        return (synthetic.isoformat(),
                (synthetic + timedelta(hours=1)).isoformat())

    def _safe_args(self, leaf: Any, args: Any) -> dict[str, Any] | None:
        if not isinstance(leaf, str):
            return None
        scoped = _scope(leaf, args)
        if scoped is None:
            return None
        required = "deviceId" if "deviceId" in scoped else "appId"
        alias = self._pseudonym("device" if required == "deviceId" else "app",
                                scoped[required])
        if not alias:
            return None
        converted: dict[str, Any] = {required: alias}
        if "since" in scoped:
            since, until = self._window(scoped["since"], scoped["until"])
            converted.update({"since": since, "until": until})
        if "attribute" in scoped:
            if scoped["attribute"] not in _ATTRIBUTES:
                return None
            converted["attribute"] = scoped["attribute"]
        for key in ("offset", "length"):
            if key in scoped:
                converted[key] = scoped[key]
        return converted

    def _prior_receipts(self, original: Sequence[Any]) -> list[dict[str, Any]]:
        projected: list[dict[str, Any]] = []
        # Only a positively scoped, previously recorded read survives.
        for receipt in original[:_MAX_PRIOR_READS]:
            if not isinstance(receipt, Mapping):
                continue
            if receipt.get("mutates") is True or receipt.get("effect") not in (None, "read"):
                continue
            if receipt.get("supports_live_claim") is False:
                continue
            leaf = receipt.get("sub_tool") or receipt.get("tool")
            if leaf not in _READ_SCOPES:
                continue
            args = self._safe_args(leaf, _args(receipt))
            if args is None:
                continue
            converted = {
                "tool": ("hub_read_apps_code" if leaf == "hub_get_app_config"
                         else "hub_read_devices"),
                "sub_tool": leaf, "effect": "read",
                "success": receipt.get("success") is True,
                "arguments": {"args": args},
            }
            if leaf == "hub_list_device_dependents" and converted["success"]:
                details = receipt.get("details")
                if isinstance(details, Mapping) and _id(details.get("deviceId")) == _id(_args(receipt).get("deviceId")):
                    apps = details.get("appsUsing")
                    aliases = []
                    if isinstance(apps, list):
                        for item in apps[:20]:
                            app_id = (item.get("appId") or item.get("id")) if isinstance(item, Mapping) else item
                            alias = self._pseudonym("app", app_id)
                            if alias:
                                aliases.append({"appId": alias})
                    converted["details"] = {
                        "deviceId": args["deviceId"], "deviceName": "Private Device",
                        "appsUsing": aliases,
                    }
            projected.append(converted)
        # Independently verified scoped identities/command issuers only.
        # These are projections, not source history or physical ACKs.
        view = build_canonical_evidence_view(original[:160])
        for identity in view.identities[:_MAX_NAMES]:
            if identity.kind != "device" or view.verified_label("device", identity.entity_id) is None:
                continue
            alias = self._pseudonym("device", identity.entity_id)
            if alias:
                projected.append({
                    "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
                    "effect": "read", "success": True,
                    "evidence_kind": "targeted_device_lookup",
                    "arguments": {"args": {}},
                    "details": {"reportedDeviceState": {
                        "source": "targeted-hubitat-device-state",
                        "deviceId": alias, "label": "Private Device",
                    }},
                })
        for event in (e for e in view.events if e.role == "issued-command"
                      and e.issuer_app_id and e.attribute in _COMMANDS):
            if sum(x.get("synthetic_issuer_projection", False) for x in projected) >= _MAX_COMMANDS:
                break
            device = self._pseudonym("device", event.entity_id)
            app = self._pseudonym("app", event.issuer_app_id)
            if device and app:
                projected.append({
                    "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
                    "effect": "read", "success": True,
                    "synthetic_issuer_projection": True,
                    "arguments": {"args": {"deviceId": device}},
                    "details": {"observedEvents": [{
                        "name": "command-" + event.attribute,
                        "date": _SYNTHETIC_START.isoformat(),
                        "producedBy": {"appId": app, "name": "Private App"},
                    }]},
                })
        return projected[:160]

    def _safe_round(
        self, receipts: Sequence[Any], calls: Sequence[Any],
        schemas: Sequence[Any],
    ) -> dict[str, Any]:
        permitted = {
            gateway: ops for gateway, ops in
            _declared_operations(schemas[:_MAX_SCHEMAS]).items()
            if gateway in _GATEWAYS
        }
        safe_schemas = []
        for gateway in sorted(permitted):
            leaves = sorted(op for op in permitted[gateway] if op in _READ_SCOPES)
            if leaves:
                safe_schemas.append({
                    "type": "function",
                    "function": {"name": gateway, "parameters": {
                        "type": "object", "properties": {
                            "tool": {"type": "string", "enum": leaves},
                        },
                    }},
                })
        safe_calls = []
        for call in calls[:_MAX_CALLS]:
            function = call.get("function") if isinstance(call, Mapping) else None
            if not isinstance(function, Mapping):
                continue
            gateway = function.get("name")
            if not isinstance(gateway, str) or gateway not in permitted:
                continue
            arguments = _call_arguments(function.get("arguments"))
            if not isinstance(arguments, Mapping):
                continue
            leaf = arguments.get("tool")
            if not isinstance(leaf, str) or leaf not in permitted[gateway]:
                continue
            safe_args = self._safe_args(leaf, arguments.get("args"))
            if safe_args is not None:
                safe_calls.append({"function": {
                    "name": gateway,
                    "arguments": {"tool": leaf, "args": safe_args},
                }})
        return {
            "receipts_before": self._prior_receipts(receipts),
            "model_tool_calls": safe_calls,
            "declared_tool_schemas": safe_schemas,
        }

    def capture_round(
        self, receipts: Sequence[Any], calls: Sequence[Any],
        schemas: Sequence[Any], *, request_identity: Any = None,
    ) -> dict[str, Any]:
        """Observe only. Never mutate arguments or propagate private errors."""
        with self._lock:
            if not self._live():
                return {"captured": False, "reason": "disabled-or-expired"}
            if self._owner is _UNBOUND:
                self._owner = request_identity
            elif self._owner is not request_identity:
                self._skipped += 1
                return {"captured": False, "reason": "different-request"}
            if len(self._rounds) >= _MAX_ROUNDS:
                self._skipped += 1
                return {"captured": False, "reason": "round-cap"}
            if not isinstance(receipts, (list, tuple)) or not isinstance(calls, (list, tuple)) or not isinstance(schemas, (list, tuple)):
                self._skipped += 1
                return {"captured": False, "reason": "invalid-round"}
            if len(receipts) > 160 or len(calls) > _MAX_CALLS or len(schemas) > _MAX_SCHEMAS:
                self._skipped += 1
                return {"captured": False, "reason": "unbounded-round"}
            try:
                row = self._safe_round(receipts, calls, schemas)
            except (TypeError, ValueError, OverflowError, AttributeError, RecursionError):
                self._skipped += 1
                return {"captured": False, "reason": "invalid-round"}
            self._rounds.append(row)
            return {"captured": True, "rounds": len(self._rounds)}

    def private_report(self) -> dict[str, Any]:
        """Export aggregate-only, never a per-round or raw replay payload."""
        with self._lock:
            if not self._live() or not self._rounds:
                return {"available": False, "reason": "disabled-expired-or-empty"}
            case = {
                "case_id": "private-capture", "domain": self._domain,
                "trace_origin": "user-labelled-redacted-trace",
                "rounds": self._rounds,
            }
            return build_stage3e_private_trace_report([case])

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = self._live()
            return {
                "enabled": active,
                "round_count": len(self._rounds) if active else 0,
                "skipped_round_count": self._skipped,
                "stored_to_disk": False,
                "uploaded": False,
                "raw_ids_names_arguments_retained": False,
                "capture_provenance_independently_verified": False,
            }


__all__ = ["LocalStage3FCapture"]
