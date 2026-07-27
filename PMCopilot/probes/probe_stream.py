"""Scratch: what does g.stream(stream_mode='updates') actually yield?

Run from PMCopilot root:  uv run python -m probes.probe_stream

Stops at the approval gate — no MCP calls, no mock writes.
"""
from datetime import datetime, timezone
from orchestrator import build_graph, make_saver

DB = "pmcopilot_demo.sqlite"
THREAD = f"probe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
CFG = {"configurable": {"thread_id": THREAD}}

g = build_graph(checkpointer=make_saver(DB))

print("pre-invoke .next:", g.get_state(CFG).next)
stream = g.stream(
    {"topic": "streaming behavior and chunk handling"}, CFG, stream_mode="updates"
)
for i, chunk in enumerate(stream):
    print(f"[{i}] keys: {list(chunk.keys())}")
    print(f"     .next after: {g.get_state(CFG).next}")
print("generator ended. .next:", g.get_state(CFG).next)
