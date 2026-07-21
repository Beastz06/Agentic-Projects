"""Smoke test for the business layer — run: uv run python -m mcp_server.slack.smoke"""
from mcp_server.slack import log
from mcp_server.slack.errors import MessageNotFoundError
from mcp_server.slack.schemas import PostMessageInput, PostThreadReplyInput


def main() -> None:
    log.init_log()

    msg = log.post_message(PostMessageInput(
        channel="#product", text="Exec digest: auth session-timeout PRD approved, filing to roadmap.",
    ))
    print("POSTED:", msg.model_dump())

    reply = log.post_thread_reply(PostThreadReplyInput(
        channel="#product", thread_ts=msg.ts, text="Roadmap item created, targeting next quarter.",
    ))
    print("REPLIED:", reply.ts, "-> parent:", reply.thread_ts)

    for label, args in [
        ("bogus ts", PostThreadReplyInput(channel="#product", thread_ts="0000000000.000000", text="ghost")),
        ("wrong channel", PostThreadReplyInput(channel="#random", thread_ts=msg.ts, text="lost")),
    ]:
        try:
            log.post_thread_reply(args)
            print(f"BUG ({label}): expected MessageNotFoundError, none raised")
        except MessageNotFoundError as e:
            print(f"OK raised ({label}): {e}")


if __name__ == "__main__":
    main()
