"""Full 4-agent pipeline with a live human approval gate.

Graph pauses at approval_gate; free text -> interpret -> confirm -> resume
(the caller-side protocol from gate_protocol.py). Loops until END.
"""
import json
from langgraph.types import Command
from gate_protocol import interpret_verdict
from orchestrator import build_graph, make_saver
from datetime import datetime, timezone

DB = "pmcopilot_demo.sqlite"
THREAD_ID = f"gate-demo-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
CFG = {"configurable": {"thread_id": THREAD_ID}}


def main() -> None:
    g = build_graph(checkpointer=make_saver(DB))
    g.invoke({"topic": "authentication"}, CFG)

    while True:
        snapshot = g.get_state(CFG)
        if not snapshot.next:          # graph reached END
            break
        payload = snapshot.tasks[0].interrupts[0].value
        print("\n=== PRD FOR REVIEW ===")
        print(json.dumps(payload["review"], indent=2))

        proposal = None
        while proposal is None:
            verdict = input("\nYour verdict (free text): ")
            proposal = interpret_verdict(verdict)
            print(f"Interpreted as: {proposal}")
            if input("Confirm? [y/n] ").strip().lower() != "y":
                proposal = None       # re-ask; human rejected the interpretation

        g.invoke(Command(resume=proposal), CFG)

    final = g.get_state(CFG).values
    print("\n=== PIPELINE COMPLETE ===")
    print("current_step:", final["current_step"])
    print("thread:", THREAD_ID)
    print("prds:", len(final["prds"]))
    print("jira_issue_id:", final.get("jira_issue_id"))
    print("notion_page_id:", final.get("notion_page_id"))
    print("slack_message_ts:", final.get("slack_message_ts"))
    print("roadmap items:", len(final["roadmap"] or []))
    print("digests:", [d.audience for d in final["digests"]])
    print("roadmap items:", len(final["roadmap"] or []))
    print("digests:", [d.audience for d in final["digests"]])
    print("errors:", final["error_messages"] if final["error_messages"] else "none")


if __name__ == "__main__":
    main()
