"""Business layer: JSONL-log-backed message store for the mock Slack. One JSON record per line,
append-only. Raises MessageNotFoundError on missing thread parents; the MCP transport converts
uncaught exceptions into readable error-results."""
import json
from datetime import datetime, timezone
from pathlib import Path
from mcp_server.slack.errors import MessageNotFoundError
from mcp_server.slack.schemas import Message, PostMessageInput, PostThreadReplyInput

LOG_PATH = Path(__file__).parent / "slack_mock.jsonl"


def init_log() -> None:
    if not LOG_PATH.exists():
        LOG_PATH.touch()


def _append(message: Message) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message.model_dump()) + "\n")


def _parent_exists(channel: str, ts: str) -> bool:
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record["channel"] == channel and record["ts"] == ts:
                return True
    return False


def _now() -> tuple[str, str]:
    instant = datetime.now(timezone.utc)
    return f"{instant.timestamp():.6f}", instant.isoformat()


def post_message(data: PostMessageInput) -> Message:
    """Post a top-level message to a channel. Returns the message with its server-assigned ts."""
    ts, posted_at = _now()
    message = Message(ts=ts, channel=data.channel, text=data.text, posted_at=posted_at)
    _append(message)
    return message


def post_thread_reply(data: PostThreadReplyInput) -> Message:
    """Post a reply into an existing thread, addressed by (channel, thread_ts).
    Raises MessageNotFoundError if no parent message matches."""
    if not _parent_exists(data.channel, data.thread_ts):
        raise MessageNotFoundError(
            f"No message found in channel {data.channel} with ts {data.thread_ts}",
            channel=data.channel,
            thread_ts=data.thread_ts,
        )
    ts, posted_at = _now()
    message = Message(
        ts=ts, channel=data.channel, text=data.text, thread_ts=data.thread_ts, posted_at=posted_at,
    )
    _append(message)
    return message
