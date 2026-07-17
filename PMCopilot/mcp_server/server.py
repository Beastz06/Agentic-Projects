"""Entrypoint: importing the tool modules registers them on the shared FastMCP instance."""
from mcp_server.app import mcp
from mcp_server.jira import tools as jira_tools  # noqa: F401 — import triggers @mcp.tool registration
from mcp_server.jira.db import init_db

if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
