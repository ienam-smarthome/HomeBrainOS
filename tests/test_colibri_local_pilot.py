"""Tests use a mocked fictional API; never run Colibri or Hubitat."""
import unittest
from unittest.mock import patch

from scripts import colibri_pilot_probe as p


class ColibriProbeTests(unittest.TestCase):
    def test_only_local_by_default(self):
        self.assertEqual(p.normalise_base("http://127.0.0.1:8000"), "http://127.0.0.1:8000/v1")
        self.assertEqual(p.normalise_base("http://localhost:8000/v1"), "http://localhost:8000/v1")
        for value in ["https://example.com/v1", "http://192.168.1.2:8000/v1",
                      "file:///etc/passwd", "http://user:pass@localhost:8000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.normalise_base(value)
        self.assertEqual(p.normalise_base("http://192.168.1.2:8000", allow_lan=True),
                         "http://192.168.1.2:8000/v1")

    def test_reject_unwanted_tools(self):
        for args in ['{}', '{"device":"real-light"}', '{broken']:
            ok, _ = p.validate_tool_calls({"tool_calls": [{"id": "x",
                "function": {"name": "get_demo_switch", "arguments": args}}]})
            self.assertFalse(ok)
        ok, _ = p.validate_tool_calls({"tool_calls": [{"id": "x",
            "function": {"name": "get_demo_switch", "arguments": '{"device":"DEMO-ONLY"}'}}]})
        self.assertTrue(ok)

    @patch.object(p, "request_json")
    def test_fake_api_roundtrip(self, request):
        request.side_effect = [
            {"data": [{"id": "test-model"}]},
            {"choices": [{"message": {"content": "This is a fictional check."}}]},
            {"choices": [{"message": {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "get_demo_switch", "arguments": '{"device":"DEMO-ONLY"}'}}]}}]},
            {"choices": [{"message": {"content": "DEMO-ONLY is off."}}]},
        ]
        result = p.run_probe("http://127.0.0.1:8000/v1", None, 5)
        self.assertTrue(result["chat_ok"])
        self.assertTrue(result["tool_call_ok"])
        self.assertTrue(result["tool_roundtrip_ok"])
        self.assertEqual(request.call_count, 4)
        for call in request.call_args_list:
            self.assertTrue(call.args[1].startswith("http://127.0.0.1:8000/v1/"))


if __name__ == "__main__":
    unittest.main()
