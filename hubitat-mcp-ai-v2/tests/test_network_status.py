import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rootfs", "app"))
from network_status import network_status, _host_port  # noqa: E402


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

    def test_host_port_parsing(self):
        self.assertEqual(_host_port("https://hub.local/mcp"), ("hub.local", 443))
        self.assertEqual(_host_port("http://10.0.0.9:8080/x"), ("10.0.0.9", 8080))
        self.assertIsNone(_host_port("not a url"))


if __name__ == "__main__":
    unittest.main()
