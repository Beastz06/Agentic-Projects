"""Scratch: what does stream_mode=['updates','debug'] yield, and does a debug
event arrive BEFORE its node executes?

Run from PMCopilot root:  uv run python -m probes.probe_debug

Answered: type='task' precedes the node's updates chunk, type='task_result'
follows it, and payload['name'] carries the node name. run_stream() in app.py
is built on that contract — this file is its reproduction case if a LangGraph
upgrade changes the debug payload shape.

Stops at the approval gate — no MCP calls, no mock writes.
"""
from datetime import datetime, timezone
from orchestrator import build_graph, make_saver

DB = "pmcopilot_demo.sqlite"
THREAD = f"probe-dbg-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
CFG = {"configurable": {"thread_id": THREAD}}

g = build_graph(checkpointer=make_saver(DB))

stream = g.stream(
    {"topic": "streaming behavior and chunk handling"},
    CFG,
    stream_mode=["updates", "debug"],
)

for i, (mode, chunk) in enumerate(stream):
    if mode == "updates":
        print(f"[{i}] updates -> {list(chunk.keys())}")
        continue

    ctype = chunk.get("type") if isinstance(chunk, dict) else None
    step = chunk.get("step") if isinstance(chunk, dict) else None
    payload = chunk.get("payload") if isinstance(chunk, dict) else None
    pkeys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
    name = payload.get("name") if isinstance(payload, dict) else None

    print(f"[{i}] debug   type={ctype!r} step={step} name={name!r}")
    print(f"     chunk keys:   {list(chunk.keys()) if isinstance(chunk, dict) else type(chunk).__name__}")
    print(f"     payload keys: {pkeys}")
