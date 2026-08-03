"""Probe: retrieval overlap matrix across candidate eval topics (C9 banding).

Assigns difficulty bands by MEASURED cross-cutting, not author intuition.
Two topics drawing the same issues are competing for the same evidence.
"""
from itertools import combinations
from rag.retriever import query

K = 8  # matches agents.discovery.RETRIEVAL_K

TOPICS = [
    # subsystem-named (expected simple)
    "authentication",
    "token counting and usage metadata",
    "streaming behavior and chunk handling",
    "tool calling and function calling",
    "retriever and vector store integrations",
    "document loaders and text splitters",
    "prompt templates and output parsers",
    # quality-attribute-named (expected ambiguous)
    "developer experience",
    "error handling and debuggability",
    "performance and latency",
    "backward compatibility and breaking changes",
    "documentation gaps",
]

sets, dists = {}, {}
for i, t in enumerate(TOPICS):
    recs = query(t, k=K)
    sets[t] = {r["number"] for r in recs}
    ds = [r["distance"] for r in recs]
    dists[t] = (min(ds), sum(ds) / len(ds), max(ds))
    print(f"[{i:>2}] {t}")
    print(f"     ids: {sorted(sets[t])}")
    print(f"     distance  min={ds[0]:.4f}  mean={dists[t][1]:.4f}  max={max(ds):.4f}")

print("\n" + "=" * 70)
print("PAIRWISE OVERLAP (shared issue ids out of %d)" % K)
print("=" * 70)
print("     " + "".join(f"{i:>4}" for i in range(len(TOPICS))))
for i, a in enumerate(TOPICS):
    row = ""
    for j, b in enumerate(TOPICS):
        row += "   -" if i == j else f"{len(sets[a] & sets[b]):>4}"
    print(f"[{i:>2}] {row}")

print("\n" + "=" * 70)
print("CROSS-CUTTING SCORE (mean overlap with all other topics)")
print("=" * 70)
scored = []
for i, a in enumerate(TOPICS):
    others = [len(sets[a] & sets[b]) for j, b in enumerate(TOPICS) if i != j]
    scored.append((sum(others) / len(others), i, a))
for score, i, t in sorted(scored, reverse=True):
    print(f"  {score:5.2f}  [{i:>2}] {t}")

print("\n" + "=" * 70)
print("HIGHEST-OVERLAP PAIRS")
print("=" * 70)
pairs = sorted(
    ((len(sets[a] & sets[b]), a, b) for a, b in combinations(TOPICS, 2)),
    reverse=True,
)
for n, a, b in pairs[:8]:
    print(f"  {n}/{K}  {a}  <->  {b}")
