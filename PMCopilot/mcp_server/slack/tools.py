"""MCP tool surface for the mock Slack. Thin wrappers: registration + docstrings only; logic lives in log."""
from mcp_server.app import mcp
from mcp_server.slack import log
from mcp_server.slack.schemas import Message, PostMessageInput, PostThreadReplyInput


@mcp.tool()
def post_message(data: PostMessageInput) -> Message:
    """Post a top-level message to a channel. Returns the posted message,
    including its server-assigned ts (use it as thread_ts to reply)."""
    return log.post_message(data)


@mcp.tool()
def post_thread_reply(data: PostThreadReplyInput) -> Message:
    """Reply to an existing message's thread, addressed by channel and the parent's ts.
    Fails if no parent message matches."""
    return log.post_thread_reply(data)
