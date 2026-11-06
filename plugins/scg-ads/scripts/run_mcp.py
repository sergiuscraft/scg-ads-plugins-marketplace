#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Launcher for the Google Ads MCP server. Reads ~/.config/scg-ads/config.toml (or SCG_ADS_CONFIG),
exports the credentials as environment variables for the server process only, then execs it.
Real environment variables win over the file. Nothing is printed (stdout is the MCP channel)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import config  # noqa: E402

cfg = config.apply_env()
fork = os.environ.get("GOOGLE_ADS_MCP_FORK_DIR")
if not fork or not (Path(fork) / "ads_mcp").is_dir():
    sys.stderr.write("scg-ads: set [mcp].fork_dir in %s (run: configure.py init)\n" % config.config_path())
    sys.exit(1)
os.execvp("uv", ["uv", "run", "--quiet", "--directory", fork, "-m", "ads_mcp.server"])
