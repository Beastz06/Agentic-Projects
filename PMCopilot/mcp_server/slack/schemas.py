from typing import Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    ts: str = Field(description="Server-assigned message timestamp id, e.g. '1753131951.252057'")
    channel: str = Field(description="Channel the message was posted to")
    text: str = Field(description="Message text")
    thread_ts: Optional[str] = Field(
        default=None,
        description="Parent message ts if this is a thread reply; absent for top-level messages",
    )
    posted_at: str = Field(description="UTC ISO timestamp when the message was posted (readable form of ts)")


class PostMessageInput(BaseModel):
    channel: str = Field(min_length=1, description="Channel to post to, e.g. '#product'")
    text: str = Field(min_length=1, description="Message text")


class PostThreadReplyInput(BaseModel):
    # Real Slack addresses a thread by (channel, thread_ts) — a ts alone is not
    # a message identity. The reply fails if no parent message matches both.
    channel: str = Field(min_length=1, description="Channel containing the parent message")
    thread_ts: str = Field(min_length=1, description="ts of the parent message to reply to")
    text: str = Field(min_length=1, description="Reply text")
