"""Full 4-agent pipeline with a live human approval gate.

Graph pauses at approval_gate; free text -> interpret -> confirm -> resume
(the caller-side protocol from gate_protocol.py). Loops until END.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import argparse
from langgraph.types import Command
from gate_protocol import interpret_verdict
from orchestrator import build_graph, make_saver
import telemetry

DB = "pmcopilot_demo.sqlite"
THREAD_ID = f"gate-demo-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
CFG = {"configurable": {"thread_id": THREAD_ID}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full pipeline with a live approval gate.")
    parser.add_argument("--topic", required=True, help="Discovery topic for this run.")
    parser.add_argument("--out", required=True, help="Path for the telemetry event dump (JSON).")
    args = parser.parse_args()

    out_path = Path(args.out)
    if out_path.exists():
        raise SystemExit(f"Refusing to overwrite an existing dump: {out_path}")

    events: list[dict] = []
    logging.getLogger(telemetry.ROOT).addHandler(
        telemetry.TelemetryHandler(
            events,
            sink=lambda e: print(f"  [{e['logger']}] {e['message']}"),
        )
    )
    logging.getLogger(telemetry.ROOT).setLevel(logging.INFO)

    g = build_graph(checkpointer=make_saver(DB))
    telemetry.stage_marker(events, "initial")
    g.invoke({"topic": args.topic}, CFG)
    telemetry.stage_marker(events, "initial", end=True)

    segment = 0
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

        segment += 1
        label = f"resume:{segment}:{proposal['action']}"
        telemetry.stage_marker(events, label)
        g.invoke(Command(resume=proposal), CFG)
        telemetry.stage_marker(events, label, end=True)

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
    print("errors:", final["error_messages"] if final["error_messages"] else "none")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "topic": args.topic,
                "thread_id": THREAD_ID,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "events": events,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("telemetry:", out_path, f"({len(events)} events)")


if __name__ == "__main__":
    main()
