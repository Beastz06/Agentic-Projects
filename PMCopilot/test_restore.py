"""Day 25 mandatory gate: do typed objects survive the checkpoint round-trip?"""
from orchestrator import build_graph, make_saver

DB = "test_restore.sqlite"
CFG = {"configurable": {"thread_id": "restore-test-1"}}

# --- Phase 1: run to a static breakpoint and persist ---
saver1 = make_saver(DB)
g1 = build_graph(checkpointer=saver1, interrupt_before=["planner"])
g1.invoke({"topic": "authentication", "prds": [], "digests": []}, CFG)
print("phase 1 complete — halted before planner")

# --- Phase 2: fresh graph over the same DB = simulated restart ---
saver2 = make_saver(DB)
g2 = build_graph(checkpointer=saver2, interrupt_before=["planner"])
snapshot = g2.get_state(CFG)

findings = snapshot.values["findings"]
prds = snapshot.values["prds"]
print("findings type:", type(findings))
print("prds[0] type:", type(prds[0]) if prds else "EMPTY")
print("current_step:", snapshot.values["current_step"])
