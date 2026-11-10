"""V2 speech/TTS contract tests; no actual microphone, Hubitat or HA requests."""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from home_assistant_tts import (
    HomeAssistantTTS, HomeAssistantTTSConfigurationError,
)


class NativeTTSContractTests(unittest.TestCase):
    def test_disabled_and_missing_token_fail_without_network(self):
        async def run():
            for enabled, token in [(False, "configured"), (True, "")]:
                tts = HomeAssistantTTS(
                    enabled=enabled, supervisor_token=token,
                    notify_service="notify.mobile_app_phone")
                with self.assertRaises(HomeAssistantTTSConfigurationError):
                    await tts.speak("hello")
            tts = HomeAssistantTTS(enabled=True, supervisor_token="configured",
                                   notify_service="notify.evil")
            with self.assertRaises(HomeAssistantTTSConfigurationError):
                await tts.speak("hello")
        asyncio.run(run())

    def test_explicit_mobile_target_and_stop_command(self):
        async def run():
            requests = []
            def respond(request):
                requests.append(request)
                return httpx.Response(200, json=[])
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                tts = HomeAssistantTTS(
                    enabled=True, supervisor_token="mock-supervisor",
                    notify_service="notify.mobile_app_my_phone",
                    client=client)
                sent = await tts.speak("A spoken answer")
                stopped = await tts.stop()
                self.assertTrue(sent["sent"])
                self.assertTrue(stopped["sent"])
                self.assertEqual(len(requests), 2)
                self.assertTrue(all(r.url.path.endswith("/services/notify/mobile_app_my_phone")
                                    for r in requests))
                self.assertEqual(requests[0].headers["authorization"],
                                 "Bearer mock-supervisor")
                self.assertEqual(requests[0].json() if hasattr(requests[0], "json") else
                                 json.loads(requests[0].content),
                                 {"message": "TTS", "data": {"tts_text": "A spoken answer"}})
                self.assertEqual(json.loads(requests[1].content),
                                 {"message": "command_stop_tts"})
        asyncio.run(run())

    def test_ambiguous_mobile_target_never_chooses_any_device(self):
        async def run():
            posts=[]
            def respond(request):
                if request.method=="GET":
                    return httpx.Response(200, json=[{"domain":"notify","services":{
                        "mobile_app_phone_one":{}, "mobile_app_phone_two":{}}}])
                posts.append(request)
                return httpx.Response(200, json=[])
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                tts=HomeAssistantTTS(enabled=True,supervisor_token="fake",client=client)
                with self.assertRaises(HomeAssistantTTSConfigurationError) as err:
                    await tts.speak("not sent")
                self.assertIn("Multiple mobile-app",str(err.exception))
                self.assertEqual(posts,[])
        asyncio.run(run())

    def test_v2_http_voice_routes_require_same_origin_ui_header(self):
        import app as runtime
        class FakeTTS:
            def __init__(self):self.calls=[]
            def status(self):return {"enabled":True,"can_attempt":True}
            async def speak(self,text):
                self.calls.append(("speak",text))
                return {"sent":True,"method":"test-transport"}
            async def stop(self):
                self.calls.append(("stop",None))
                return {"sent":True}
        async def run():
            prior=getattr(runtime.app.state, "tts", None)
            fake=FakeTTS()
            runtime.app.state.tts=fake
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.app),
                                             base_url="http://test") as client:
                    denied=await client.post("/api/tts",json={"text":"hello"})
                    self.assertEqual(denied.status_code,403)
                    denied_stop=await client.post("/api/tts/stop")
                    self.assertEqual(denied_stop.status_code,403)
                    empty=await client.post("/api/tts",json={"text":""},
                         headers={"X-Homebrain-Request":"1"})
                    self.assertEqual(empty.status_code,422)
                    too_long=await client.post("/api/tts",json={"text":"a"*1501},
                         headers={"X-Homebrain-Request":"1"})
                    self.assertEqual(too_long.status_code,422)
                    self.assertEqual(fake.calls,[])
                    ok=await client.post("/api/tts",json={"text":"A safe test"},
                         headers={"X-Homebrain-Request":"1"})
                    self.assertEqual(ok.status_code,200)
                    self.assertTrue(ok.json()["success"])
                    stopped=await client.post("/api/tts/stop",
                         headers={"X-Homebrain-Request":"1"})
                    self.assertEqual(stopped.status_code,200)
                    self.assertEqual(fake.calls,[("speak","A safe test"),("stop",None)])
            finally:
                if prior is None:del runtime.app.state.tts
                else:runtime.app.state.tts=prior
        asyncio.run(run())


if __name__=="__main__":
    unittest.main()
