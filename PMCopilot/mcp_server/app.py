"""Single FastMCP instance shared by all tool families (Jira, Notion, Slack),
plus the root directory the mock stores write into."""
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pmcopilot-mcp")

# Root for the mock stores; each family writes to its own subdirectory beneath it.
# Defaults to the package directory, which is correct for a cloned repo. Set
# PMCOPILOT_MCP_DATA_DIR when the package lives somewhere read-only (a pip install
# into site-packages) or when the data should outlive a reinstall.
DATA_ROOT = Path(os.environ.get("PMCOPILOT_MCP_DATA_DIR", Path(__file__).parent))