"""Single FastMCP instance shared by all tool families (Jira, Notion, Slack)."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pmcopilot-mcp")
