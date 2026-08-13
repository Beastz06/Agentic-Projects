"""MCP client access for the orchestrator: reaches the PMCopilot MCP server over stdio.

Each call opens a fresh session (spawn -> handshake -> call -> teardown); the
server's SQLite file carries persistence across sessions. Tools are async-only
in langchain-mcp-adapters, so this module owns the sync bridge for graph nodes.
"""
import asyncio
import json
import os
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient


def _child_env() -> dict | None:
    """Environment for the server subprocess, or None to inherit the adapter's default.

    The stdio client does not pass the parent environment through, so the one
    variable the server actually reads has to be forwarded explicitly. Windows
    needs SYSTEMROOT and PATH alongside it or the interpreter fails to start.
    """
    data_dir = os.environ.get("PMCOPILOT_MCP_DATA_DIR")
    if data_dir is None:
        return None
    env = {"PMCOPILOT_MCP_DATA_DIR": data_dir}
    for key in ("SYSTEMROOT", "PATH"):
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    return env


SERVER_CONFIG = {
    "pmcopilot": {
        "command": sys.executable,
        "args": ["-m", "mcp_server.server"],
        "transport": "stdio",
        "env": _child_env(),
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
