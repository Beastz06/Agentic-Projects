"""Entrypoint: importing the tool modules registers them on the shared FastMCP instance."""
from mcp_server.app import mcp
from mcp_server.jira import tools as jira_tools  # noqa: F401 — import triggers @mcp.tool registration
from mcp_server.jira.db import init_db
from mcp_server.notion import tools as notion_tools  # noqa: F401 — import triggers @mcp.tool registration
from mcp_server.notion.store import init_store
from mcp_server.slack import tools as slack_tools  # noqa: F401 — import triggers @mcp.tool registration
from mcp_server.slack.log import init_log

if __name__ == "__main__":
    init_db()
    init_store()
    init_log()
    mcp.run(transport="stdio")
