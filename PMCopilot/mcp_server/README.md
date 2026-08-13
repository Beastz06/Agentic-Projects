# PMCopilot MCP Server

A single MCP server exposing three families of mock filing tools — Jira, Notion,
and Slack — over stdio. The backends are local: SQLite for Jira, a JSON file for
Notion, an append-only JSONL log for Slack. Nothing talks to a real service.

## Tools

| Family | Tools |
|---|---|
| Jira | `create_issue`, `list_issues`, `get_issue`, `update_status`, `add_comment` |
| Notion | `create_page`, `list_pages`, `update_page` |
| Slack | `post_message`, `post_thread_reply` |

Every tool takes a single `data` argument wrapping its input model — for example
`list_issues` is called as `{"data": {}}`, not `{}`. Claude Desktop handles this
from the schema; direct programmatic callers need to nest explicitly.

## Running it from Claude Desktop

Add this to `claude_desktop_config.json` (Settings → Developer → Edit Config),
substituting your own clone path in both places:

```json
{
  "mcpServers": {
    "pmcopilot": {
      "command": "C:\\path\\to\\PMCopilot\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\path\\to\\PMCopilot"
    }
  }
}
```

`cwd` is required. `mcp_server` is a package inside the repo rather than an
installed distribution, so a server started from anywhere else fails at import
with `No module named 'mcp_server'`, which Claude Desktop reports only as a
failure to start.

On macOS and Linux the interpreter is `.venv/bin/python` and paths use forward
slashes.

Restart Claude Desktop after editing the config. The tools appear under the
connector menu once the server handshakes.

## Where the data goes

Each family writes into its own subdirectory of `mcp_server/`:

```
mcp_server/jira/jira_mock.sqlite
mcp_server/notion/notion_mock.json
mcp_server/slack/slack_mock.jsonl
```

Set `PMCOPILOT_MCP_DATA_DIR` to relocate all three under a different root —
useful when the package sits somewhere read-only, or when the data should
survive a reinstall. Missing directories are created on import.

```json
{
  "mcpServers": {
    "pmcopilot": {
      "command": "C:\\path\\to\\PMCopilot\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\path\\to\\PMCopilot",
      "env": { "PMCOPILOT_MCP_DATA_DIR": "C:\\path\\to\\writable\\dir" }
    }
  }
}
```