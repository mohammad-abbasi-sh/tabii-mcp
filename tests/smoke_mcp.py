"""MCP stdio smoke: spawn the server as a real MCP client would and
call three tools live.

Run: python tests/smoke_mcp.py

The MCP stdio client spawns the server with a MINIMAL environment
(HOME, LOGNAME, PATH, SHELL, TERM, USER only). On this VM, outbound
HTTPS goes through an egress proxy, so the proxy/CA variables must
be passed explicitly or the server's requests are reset mid-TLS
(curl 35). This script forwards just those variables from the
current process environment (values are never written to the repo);
on a normal machine with direct internet they are simply absent
and the server works without them.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_PROXY_VARS = (
    "https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY",
    "CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
    "no_proxy", "NO_PROXY",
)


async def main() -> int:
    env = {k: os.environ[k] for k in _PROXY_VARS if k in os.environ}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tabii_mcp.server"],
        env=env or None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)
            assert "tabii_search_content" in names
            assert "tabii_get_show" in names
            assert "tabii_live_channels" in names
            r = await s.call_tool(
                "tabii_search_content",
                {"query": "gassal", "language": "en", "limit": 3},
            )
            d = json.loads(r.content[0].text)
            assert "error" not in d, d
            print("search (gassal):", [(x["id"], x["title"]) for x in d["results"]])
            assert d["results"][0]["id"] == 438813
            r = await s.call_tool("tabii_live_channels", {"language": "tr"})
            d = json.loads(r.content[0].text)
            assert "error" not in d, d
            print("live channels:", d["count"], "first:", d["channels"][0]["title"])
            assert d["count"] == 15
            r = await s.call_tool("tabii_health", {})
            d = json.loads(r.content[0].text)
            assert "error" not in d, d
            print("health:", d["status"])
            assert d["status"] == "ok"
    print("smoke_mcp OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
