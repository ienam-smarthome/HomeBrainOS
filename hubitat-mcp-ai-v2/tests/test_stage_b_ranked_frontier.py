"""Fictional V2 Stage B offline replay of alpha.141 source shape.

Independent expected next reads are defined in tests, not passed to ranker.
Source IDs, timestamps and 201-device inventory are synthetic. No real hub,
network, cloud, native commands, or household data are accessed.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from causal_stage_b_frontier import stage_b_read_frontier, stage_b_source_allowed
from investigation_review import read_only_review_catalog

EVENTS = {
    "type": "function", "function": {
        "name": "hub_list_device_events",
        "parameters": {"type": "object", "properties": {
            "deviceId": {"type": "string"},
            "attribute": {"type": "string"},
            "since": {"type": "string"},
            "until": {"type": "string"},
            "limit": {"type": "integer"},
        }, "required": ["deviceId"]},
    },
}
LOGS = {
    "type": "function", "function": {
        "name": "hub_get_logs", "parameters": {"type": "object",
          "properties": {
            "appId": {"type": "integer"}, "mode": {"type": "string",
              "enum": ["past", "live"]},
            "since": {"type": "string"}, "until": {"type": "string"},
            "limit": {"type": "integer"},
          }, "required": ["mode"]},
    },
}
WRITER = {"type": "function", "function": {
    "name": "hub_call_device_command",
    "parameters": {"type": "object", "properties": {
        "deviceId": {"type": "string"}, "command": {"type": "string"}}},
}}
CATALOG = read_only_review_catalog([EVENTS, LOGS, WRITER])


def receipt(name, args, native, success=True):
    return {
        "name": name, "arguments": args, "success": success,
        "result_kind": "tool_result",
        "response": json.dumps({"content": [{
            "type": "text", "text": json.dumps(native)
        }]}),
    }


def inventory():
    devices = [
        {"id": str(i), "label": "Other device " + str(i),
         "room": "Shared grouping",
         "currentStates": {"switch": "off"}}
        for i in range(1000, 1194)
    ]
    devices.extend([
        {"id": "4382", "label": "Fixture thermostat",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "5311", "label": "Fixture sensor A",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "5309", "label": "Fixture sensor B",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "7748", "label": "Fixture sensor C",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "7331", "label": "Fixture sensor D",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "4718", "label": "Fixture sensor E",
         "room": "Thermostat and TRVs",
         "currentStates": {"thermostatOperatingState": "idle"}},
        {"id": "9999", "label": "Unrelated switch with same room",
         "room": "Thermostat and TRVs",
         "currentStates": {"switch": "off"}},
    ])
    return receipt("hub_list_devices", {"format": "summary"},
                   {"devices": devices, "count": len(devices)})


def event(field, value, at, listeners=None, **extras):
    item = {"name": field, "value": value, "type": "event", "date": at,
            "producedBy": {"deviceId": "4382"}}
    if listeners is not None:
        item["triggered"] = listeners
    item.update(extras)
    return item


LISTENERS = [
    {"appId": 2706, "name": "Fixture heating alert"},
    {"appId": 4129, "name": "Fixture status"},
    {"appId": 4053, "name": "Fixture external API"},
    {"appId": 613, "name": "Fixture demand scheduler"},
]
T_HEAT = "2030-11-17T07:58:47.423+00:00"
T_IDLE = "2030-11-17T08:00:49.222+00:00"
OLD_HEAT = "2030-11-17T07:17:42.585+00:00"
OLD_IDLE = "2030-11-17T07:25:05.821+00:00"


def output_history(attribute="thermostatOperatingState", device="4382"):
    return receipt("hub_list_device_events",
                   {"deviceId": device, "attribute": attribute,
                    "hoursBack": 24, "limit": 10},
                   {"source": "device", "deviceId": device,
                    "device": "Fixture thermostat",
                    "events": [
                        event(attribute, "idle", T_IDLE, LISTENERS),
                        event(attribute, "heating", T_HEAT, LISTENERS),
                        event(attribute, "idle", OLD_IDLE),
                        event(attribute, "heating", OLD_HEAT),
                    ]})


def zero_broad(*, oldest=None):
    native = {"mode": "past", "matched": 0, "total": 11906, "entries": []}
    if oldest:
        native["oldestRetainedTimestamp"] = oldest
    return receipt("hub_get_logs",
                   {"mode": "past", "since": "2030-11-17T07:50:00+00:00",
                    "until": "2030-11-17T08:10:00+00:00", "limit": 100},
                   native)


def alpha141_replay():
    return [inventory(), output_history(), zero_broad()]


def precision_replay(expected, ranked, k=3):
    # Test-only oracle! Never passed back into the source ranker.
    top = [(x["leaf"], x["category"]) for x in ranked[:k]]
    useful = [v in expected for v in top]
    return {
        "precision_at_k": sum(useful)/len(top) if top else None,
        "useful_read_rate": sum(useful)/len(top) if top else None,
        "first_useful_rank": next((i+1 for i, ok in enumerate(useful) if ok), None),
    }


class StageBOriginalSourceReplayTests(unittest.TestCase):
    def test_alpha141_three_receipt_replay_prefers_same_device_unfiltered(self):
        original = alpha141_replay()
        copy = deepcopy(original)
        ranked = stage_b_read_frontier(original, CATALOG)
        self.assertEqual(original, copy)
        self.assertEqual(ranked["status"], "ranked_original_source_candidates")
        self.assertEqual(ranked["focal"]["device_id"], "4382")
        self.assertEqual(ranked["focal"]["observed_attribute"],
                         "thermostatOperatingState")
        first = ranked["ranked_reads"][0]
        self.assertEqual(first["category"],
                         "same_output_unfiltered_command_and_state_history")
        self.assertEqual(first["leaf"], "hub_list_device_events")
        self.assertEqual(first["arguments"]["deviceId"], "4382")
        self.assertNotIn("attribute", first["arguments"])
        self.assertIn("since", first["arguments"])
        self.assertIn("until", first["arguments"])
        self.assertTrue(stage_b_source_allowed(
            ranked, first["leaf"], first["arguments"]))
        self.assertTrue(ranked["empty_broad_log_scoped_recovery_eligible"])
        self.assertNotIn("hub_call_device_command", json.dumps(ranked))
        metric = precision_replay({(
            "hub_list_device_events",
            "same_output_unfiltered_command_and_state_history",
        )}, ranked["ranked_reads"])
        self.assertEqual(metric["first_useful_rank"], 1)
        self.assertGreater(metric["useful_read_rate"], 0)

    def test_scope_capabilities_from_full_inventory_are_not_causal_rooms(self):
        ranked = stage_b_read_frontier(alpha141_replay(), CATALOG)
        scope = ranked["scope_candidates"]
        self.assertEqual(scope["full_original_inventory_reads_inspected"], 1)
        self.assertEqual(scope["eligible_capability_device_count"], 6)
        ids = {r["device_id"] for r in scope["candidates"]}
        self.assertEqual(ids, {"4382","5311","5309","7748","7331","4718"})
        self.assertNotIn("9999", ids)
        self.assertTrue(scope["room_label_not_used_as_causal_identity"])
        self.assertEqual(ranked["causal_app_candidates"][
            "recorded_command_issuers"], [])
        listeners = ranked["causal_app_candidates"][
            "notified_listener_candidates_not_issuers"]
        self.assertEqual({v["id"] for v in listeners},
                         {"2706","4129","4053","613"})
        self.assertTrue(all(x["only_notified_not_an_issuer"] for x in listeners))

    def test_unscoped_zero_does_not_prove_outside_retention(self):
        x = stage_b_read_frontier(alpha141_replay(), CATALOG)
        retention = x["log_retention"]
        self.assertEqual(retention["classification"],
                         "empty_result_scope_or_retention_unknown")
        self.assertIsNone(retention["explicit_oldest_retained_timestamp"])
        self.assertTrue(retention["empty_general_log_query_seen"])
        self.assertTrue(retention[
            "matched_zero_not_evidence_of_absent_controller_execution"])
        self.assertFalse(x["candidate_not_proof_of_actual_trigger_or_physical_effect"] is False)

    def test_explicit_retention_boundary_stops_app_log_futile_reads(self):
        rows = [inventory(), output_history(),
                zero_broad(oldest="2030-11-17T10:00:00+00:00")]
        x = stage_b_read_frontier(rows, CATALOG)
        self.assertEqual(x["log_retention"]["classification"],
                         "outside_retention_source_explicit")
        self.assertFalse(x["empty_broad_log_scoped_recovery_eligible"])
        self.assertEqual([r["category"] for r in x["ranked_reads"]],
                         ["same_output_unfiltered_command_and_state_history"])

    def test_without_explicit_retention_boundary_never_claims_age_out(self):
        for total in (0, 11906, 100000):
            with self.subTest(total=total):
                source = zero_broad()
                outer = json.loads(source["response"])
                data = json.loads(outer["content"][0]["text"])
                data["total"] = total
                outer["content"][0]["text"] = json.dumps(data)
                source["response"] = json.dumps(outer)
                x = stage_b_read_frontier([output_history(), source], CATALOG)
                self.assertNotIn("outside_retention",
                                 x["log_retention"]["classification"])

    def test_recorded_issuer_app_rank_above_listener_and_no_duplicate(self):
        cmd = {"name": "command-setHeatingSetpoint", "type": "command",
               "date": "2030-11-17T07:58:28.800+00:00",
               "producedBy": {"appId": 613}}
        hist = output_history()
        native = json.loads(json.loads(hist["response"])["content"][0]["text"])
        native["events"].insert(0, cmd)
        hist["response"] = json.dumps({
            "content":[{"type":"text","text":json.dumps(native)}]})
        x = stage_b_read_frontier([hist], CATALOG)
        categories = [r["category"] for r in x["ranked_reads"]]
        self.assertEqual(categories[0],
                         "same_output_unfiltered_command_and_state_history")
        self.assertEqual(categories[1], "recorded_command_issuer_app_log")
        issuer = x["ranked_reads"][1]
        self.assertEqual(issuer["arguments"]["appId"], 613)
        self.assertTrue(stage_b_source_allowed(x, issuer["leaf"],
                                                issuer["arguments"]))
        self.assertNotIn("hub_call_device_command", json.dumps(x))
        retry = receipt("hub_get_logs", issuer["arguments"],
                        {"mode":"past","matched":0,"entries":[]})
        y = stage_b_read_frontier([hist, retry], CATALOG)
        self.assertNotIn(613, [
            a["arguments"].get("appId") for a in y["ranked_reads"]])

    def test_empty_broad_log_recovers_recorded_issuer_even_without_listeners(self):
        historical = receipt("hub_list_device_events",
            {"deviceId":"FX-LAMP","attribute":"switch","limit":10},
            {"source":"device","deviceId":"FX-LAMP","device":"Fixture lamp",
             "events":[
                {"name":"switch","value":"off","type":"event",
                 "date":"2030-11-17T07:58:47.423+00:00"},
                {"name":"switch","value":"on","type":"event",
                 "date":"2030-11-17T07:57:47.423+00:00"},
                {"name":"command-off","type":"command",
                 "date":"2030-11-17T07:58:46.423+00:00",
                 "producedBy":{"appId":613}},
             ]})
        result=stage_b_read_frontier([historical,zero_broad()],CATALOG)
        self.assertTrue(result["empty_broad_log_scoped_recovery_eligible"])
        self.assertEqual(result["causal_app_candidates"][
            "notified_listener_candidates_not_issuers"],[])
        self.assertEqual(result["causal_app_candidates"][
            "recorded_command_issuers"],["613"])
        self.assertEqual(result["ranked_reads"][1]["category"],
                         "recorded_command_issuer_app_log")

    def test_scoped_app_retention_boundary_does_not_prove_global_aging(self):
        a=receipt("hub_get_logs",
            {"appId":613,"mode":"past",
             "since":"2030-11-17T07:50:00+00:00",
             "until":"2030-11-17T08:10:00+00:00"},
            {"mode":"past","matched":0,"entries":[],
             "oldestRetainedTimestamp":"2030-11-17T11:00:00+00:00"})
        result=stage_b_read_frontier([output_history(),zero_broad(),a],CATALOG)
        self.assertEqual(result["log_retention"]["classification"],
                         "empty_result_scope_or_retention_unknown")
        self.assertTrue(result["empty_broad_log_scoped_recovery_eligible"])

    def test_unfiltered_read_already_attempted_suppresses_duplicate(self):
        original = alpha141_replay()
        unfiltered = output_history()
        unfiltered["arguments"].pop("attribute")
        ranked = stage_b_read_frontier(original+[unfiltered], CATALOG)
        self.assertFalse(any(r["category"].startswith("same_output_unfiltered")
                             for r in ranked["ranked_reads"]))

    def test_recovery_rejects_broad_unscoped_and_spoofed_ids(self):
        ranked = stage_b_read_frontier(alpha141_replay(), CATALOG)
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_get_logs", {"mode":"past","limit":100}))
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_get_logs", {"mode":"past","appId":999}))
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_list_device_events",
            {"deviceId":"7331","limit":20}))
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_list_device_events",
            {"deviceId":"4382","attribute":"temperature","limit":20}))
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_list_device_events",
            {"deviceId":"4382","since":"2030-01-01T00:00:00+00:00"}))
        self.assertFalse(stage_b_source_allowed(
            ranked, "hub_call_device_command",
            {"deviceId":"4382","command":"off"}))
        self.assertEqual(ranked["read_limits"]["max_stage_b_recovery_reads"],2)

    def test_cross_domain_light_and_fan_same_output_ranked_first(self):
        for device,attr,lower,upper in (
            ("FX-LAMP","switch","off","on"),
            ("FX-FAN","fanOperatingState","idle","running"),
        ):
            with self.subTest(attr=attr):
                hist = receipt("hub_list_device_events",
                   {"deviceId":device,"attribute":attr},
                   {"source":"device","deviceId":device,
                    "device":"Fictional controlled output",
                    "events":[
                      {"name":attr,"value":lower,
                       "date":"2030-11-17T09:20:00+00:00"},
                      {"name":attr,"value":upper,
                       "date":"2030-11-17T09:18:00+00:00",
                       "triggered":[{"appId":777}]}]})
                out=stage_b_read_frontier([hist],CATALOG)
                self.assertEqual(out["ranked_reads"][0]["category"],
                                 "same_output_unfiltered_command_and_state_history")
                self.assertEqual(out["focal"]["device_id"],device)
                self.assertEqual(out["causal_app_candidates"][
                    "recorded_command_issuers"], [])

    def test_negative_control_cannot_invent_initiator(self):
        # No logs, no command event, and no registered listener:
        # the source ranker does not promote a causal claim.
        hist = receipt("hub_list_device_events",
                       {"deviceId":"FX-PUMP","attribute":"switch"},
                       {"source":"device","deviceId":"FX-PUMP",
                        "device":"Fictional pump",
                        "events":[{"name":"switch","value":"on",
                           "date":"2030-11-17T09:18:00+00:00"}]})
        out=stage_b_read_frontier([hist],CATALOG)
        self.assertEqual(out["causal_app_candidates"]["recorded_command_issuers"],[])
        self.assertFalse(out["empty_broad_log_scoped_recovery_eligible"])
        self.assertTrue(out["candidate_not_proof_of_actual_trigger_or_physical_effect"])
        self.assertTrue(out["native_tool_issued_by_this_index"] is False)


if __name__ == "__main__":
    unittest.main()
