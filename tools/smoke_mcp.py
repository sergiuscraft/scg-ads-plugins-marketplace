#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fastmcp>=4.0.6,<5"]
# ///
"""Start the Google Ads MCP server over stdio, list its tools and make one read-only call.

Starts it exactly like the plugin does (scripts/run_mcp.py), so it reads ~/.config/scg-ads/config.toml
(run scripts/configure.py init first). Nothing is written to your account.
"""
import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

launcher = Path(__file__).resolve().parents[1] / "plugins" / "scg-ads" / "scripts" / "run_mcp.py"


async def main() -> int:
    transport = StdioTransport(command="uv", args=["run", "--script", str(launcher)], env=dict(os.environ))
    async with Client(transport) as c:
        tools = await c.list_tools()
        print(f"OK: server started, {len(tools)} tools")
        r = await c.call_tool("customers_list_accessible_customers", {}, raise_on_error=False)
        text = r.content[0].text if r.content else ""
        if r.is_error:
            print("Tool call failed (server runs, but API access does not):\n", text[:500])
            return 1
        print("OK: accessible customers:", text[:300])
    return 0


sys.exit(asyncio.run(main()))
