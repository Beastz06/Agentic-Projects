class MessageNotFoundError(Exception):
    """Raised when no message exists for the given (channel, thread_ts)."""

    def __init__(self, message: str, channel: str, thread_ts: str):
        super().__init__(message)
        self.channel = channel
        self.thread_ts = thread_ts
