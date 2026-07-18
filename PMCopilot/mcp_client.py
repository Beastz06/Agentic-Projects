"""MCP client access for the orchestrator: reaches the PMCopilot MCP server over stdio.

Each call opens a fresh session (spawn -> handshake -> call -> teardown); the
server's SQLite file carries persistence across sessions. Tools are async-only
in langchain-mcp-adapters, so this module owns the sync bridge for graph nodes.
"""
import asyncio
import json
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient

SERVER_CONFIG = {
    "pmcopilot": {
        "command": sys.executable,
        "args": ["-m", "mcp_server.server"],
        "transport": "stdio",
    }
}


def _result_to_dict(result) -> dict:
    """Adapter returns MCP content blocks: a list of {'type': 'text', 'text': <json>} dicts."""
    if isinstance(result, list):
        result = result[0]
    if isinstance(result, dict):
        result = result["text"]
    elif not isinstance(result, str):
        result = getattr(result, "text", str(result))
    return json.loads(result)


def call_tool(name: str, args: dict) -> dict:
    """Invoke one MCP tool synchronously and return its parsed JSON payload.

    Raises on transport failure, unknown tool name, or an error-flagged tool
    result — callers treat any raise as an operational failure.
    """
    async def _call():
        client = MultiServerMCPClient(SERVER_CONFIG)
        tools = await client.get_tools()
        try:
            tool = next(t for t in tools if t.name == name)
        except StopIteration:
            raise ValueError(f"MCP server exposes no tool named '{name}'")
        return await tool.ainvoke(args)

    return _result_to_dict(asyncio.run(_call()))
