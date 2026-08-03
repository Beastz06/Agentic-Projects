"""Probe: what specificity survives into a persisted DiscoveryFinding."""
import sqlite3
from orchestrator import build_graph, make_saver

DB = "pmcopilot_demo.sqlite"

threads = [r[0] for r in sqlite3.connect(DB).execute(
    "SELECT DISTINCT thread_id FROM checkpoints")]
print(f"{len(threads)} thread(s) in {DB}\n")

graph = build_graph(checkpointer=make_saver(DB))


def get(obj, name):
    """Checkpoint restore may hand back dicts instead of models (Day 24 risk)."""
    return getattr(obj, name) if hasattr(obj, name) else obj[name]


for t in threads:
    state = graph.get_state({"configurable": {"thread_id": t}})
    finding = state.values.get("findings")
    if finding is None:
        print(f"--- {t}: no findings")
        continue
    print(f"=== {t}")
    print(f"    type on restore: {type(finding).__name__}")
    print(f"    theme: {get(finding, 'theme')}")
    for pp in get(finding, "pain_points"):
        print(f"    [{get(pp, 'severity'):>6}] ids={get(pp, 'evidence_issue_ids')}")
        print(f"             cluster: {get(pp, 'cluster')}")
    print(f"    seed: {get(finding, 'suggested_prd_seed')}\n")
