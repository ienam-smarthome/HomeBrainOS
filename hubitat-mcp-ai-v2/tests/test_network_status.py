import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rootfs", "app"))
from network_status import network_status, _host_port, clean_host  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def fakes(up_hosts, dns=True, ping_up=()):
    async def connect(host, port, timeout):
        return 5.0 if host in up_hosts else None

    async def ping(host):
        return 2.0 if host in ping_up else None

    async def resolver():
        return dns
    return dict(connect=connect, ping=ping, dns=resolver)


class NetworkStatus(unittest.TestCase):
    def test_all_up(self):
        out = run(network_status("http://192.168.1.50/mcp", "192.168.1.1",
                                 **fakes({"1.1.1.1", "8.8.8.8", "192.168.1.50"}, ping_up={"192.168.1.1"})))
        self.assertEqual(out["level"], "ok")
        self.assertTrue(all(c["ok"] for c in out["checks"]))

    def test_router_up_internet_down(self):
        out = run(network_status("", "192.168.1.1", **fakes({"192.168.1.1"}, dns=False)))
        self.assertEqual(out["level"], "bad")
        self.assertIn("Router reachable, internet not reachable", out["summary"])

    def test_router_down(self):
        out = run(network_status("", "192.168.1.1", **fakes(set(), dns=False)))
        self.assertIn("Router not reachable", out["summary"])

    def test_dns_only_failure_warns(self):
        out = run(network_status("", "", **fakes({"1.1.1.1"}, dns=False)))
        self.assertEqual(out["level"], "warn")

    def test_hub_down_is_reported(self):
        out = run(network_status("http://10.0.0.9:8080/x", "", **fakes({"1.1.1.1"})))
        self.assertIn("Hubitat hub not reachable", out["summary"])
        self.assertEqual(out["level"], "bad")

    def test_router_down_with_internet_up_is_a_warning_naming_the_attempts(self):
        out = run(network_status("", "192.168.1.1", **fakes({"1.1.1.1", "8.8.8.8"})))
        self.assertEqual(out["level"], "warn")
        self.assertIn("router address did not answer", out["summary"])
        router = next(c for c in out["checks"] if c["name"] == "Router")
        self.assertIn("tcp 80/443/53/22", router["method"])

    def test_router_value_is_cleaned(self):
        self.assertEqual(clean_host("http://192.168.1.1/"), "192.168.1.1")
        self.assertEqual(clean_host(" 192.168.1.1:8080 "), "192.168.1.1")
        self.assertEqual(clean_host(""), "")
        out = run(network_status("", "http://192.168.1.1/", **fakes({"1.1.1.1", "192.168.1.1"})))
        self.assertTrue(next(c for c in out["checks"] if c["name"] == "Router")["ok"])

    def test_host_port_parsing(self):
        self.assertEqual(_host_port("https://hub.local/mcp"), ("hub.local", 443))
        self.assertEqual(_host_port("http://10.0.0.9:8080/x"), ("10.0.0.9", 8080))
        self.assertIsNone(_host_port("not a url"))


if __name__ == "__main__":
    unittest.main()


from network_status import NetworkWatch, active_problems  # noqa: E402


def result(internet=True, hub=True, router=True):
    checks = [{"name": "Internet · Cloudflare", "ok": internet}, {"name": "Internet · Google DNS", "ok": internet},
              {"name": "Hubitat hub", "ok": hub}, {"name": "Router", "ok": router}]
    return {"checks": checks, "summary": "Internet not reachable" if not internet else "Internet reachable"}


class Harness:
    def __init__(self, **kw):
        self.now, self.res, self.sent, self.fail = 0.0, result(), [], False

        async def check():
            return self.res

        async def notify(title, message):
            if self.fail:
                raise OSError("offline")
            self.sent.append((title, message))
        self.watch = NetworkWatch(check, notify, clock=lambda: self.now, **kw)

    def at(self, minutes, res=None):
        self.now = minutes * 60.0
        if res is not None:
            self.res = res
        run(self.watch.tick())


class NetworkWatchTests(unittest.TestCase):
    def test_warn_level_router_is_not_a_problem(self):
        self.assertEqual(active_problems(result(router=False)), {})

    def test_no_alert_inside_grace_then_one_alert_and_one_recovery(self):
        h = Harness()
        h.at(0, result(internet=False))
        h.at(4)
        self.assertEqual(h.sent, [])
        h.at(5)
        h.at(9)
        self.assertEqual(len(h.sent), 1)
        self.assertIn("Internet problem", h.sent[0][0])
        h.at(12, result())
        self.assertEqual(len(h.sent), 2)
        self.assertIn("recovered", h.sent[1][0])
        self.assertIn("12 min", h.sent[1][1])

    def test_short_blip_and_hub_reboot_stay_silent(self):
        h = Harness()
        h.at(0, result(hub=False))
        h.at(7)
        self.assertEqual(h.sent, [])  # hub allowance is longer than 5 minutes
        h.at(8, result())
        self.assertEqual(h.sent, [])  # recovered inside grace: no alert, no recovery message

    def test_hub_alert_after_its_own_grace(self):
        h = Harness()
        h.at(0, result(hub=False))
        h.at(8)
        self.assertEqual(len(h.sent), 1)
        self.assertIn("Hubitat hub", h.sent[0][0])

    def test_undelivered_alert_is_retried_not_lost(self):
        h = Harness()
        h.fail = True
        h.at(0, result(internet=False))
        h.at(6)
        self.assertEqual(h.sent, [])
        self.assertEqual(h.watch.status()["undelivered"], 1)
        h.fail = False
        h.at(7)
        self.assertEqual(len(h.sent), 1)
        self.assertEqual(h.watch.status()["undelivered"], 0)

    def test_check_exception_does_not_stop_watch(self):
        async def boom():
            raise RuntimeError("x")
        w = NetworkWatch(boom, lambda t, m: None)
        run(w.tick())
        self.assertIn("check failed", w.status()["last_error"])


class PushTests(unittest.TestCase):
    def test_push_posts_text_notification_without_tts_enabled(self):
        import httpx
        from home_assistant_tts import HomeAssistantTTS
        seen = []

        def handler(request):
            seen.append((request.url.path, request.read()))
            return httpx.Response(200, json=[])
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        tts = HomeAssistantTTS(enabled=False, supervisor_token="t",
                               notify_service="notify.mobile_app_phone", client=client)
        out = run(tts.push("Title", "Body"))
        self.assertEqual(out["service"], "notify.mobile_app_phone")
        self.assertEqual(seen[0][0], "/core/api/services/notify/mobile_app_phone")
        self.assertIn(b'"Title"', seen[0][1])
        self.assertFalse(tts.enabled)
