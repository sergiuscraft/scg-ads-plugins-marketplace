#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["fastmcp>=4.0.6,<5"]
# ///
"""Start the Google Ads MCP server over stdio, list its tools and make one read-only call.

Needs GOOGLE_ADS_MCP_FORK_DIR (path to the cloned fork) and the credentials env vars
(GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_ADS_LOGIN_CUSTOMER_ID, GOOGLE_ADS_DEVELOPER_TOKEN).
Nothing is written to your account.
"""
import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

fork = os.environ.get("GOOGLE_ADS_MCP_FORK_DIR")
if not fork or not os.path.isdir(fork):
    sys.exit("Set GOOGLE_ADS_MCP_FORK_DIR to the cloned google-ads-mcp directory.")
missing = [v for v in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_ADS_LOGIN_CUSTOMER_ID") if not os.environ.get(v)]
if missing:
    sys.exit(f"Missing env vars: {', '.join(missing)} (see plugins/scg-ads/docs/PREREQS.md)")


async def main() -> int:
    transport = StdioTransport(command="uv", args=["run", "--directory", fork, "-m", "ads_mcp.server"], env=dict(os.environ))
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
