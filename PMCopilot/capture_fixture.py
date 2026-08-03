"""Capture the C9 eval fixture: 10 scenarios, frozen at one commit.

Fixture unit is FROZEN, not live: the judge is the only moving part during
Day 32 rubric tuning, so a score change has exactly one possible cause.

retrieved_issues is not checkpointed by the pipeline — research() calls
query() internally and discards it. It is re-derived here and HARD-ASSERTED
against the ID sets recorded by the overlap probe. A fixture built on
unverified retrieval would contaminate every score in the suite.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
import config
from rag.retriever import query
from schemas.discovery import DiscoveryFinding
from agents.prd_drafter import draft_prd

K = 8
FINDINGS_IN = "evals/candidate_findings.json"
OUT = "evals/fixture_v1.json"

# topic -> (band, overlap_score, expected retrieved ids from the overlap probe)
SCENARIOS = {
    "authentication": (
        "simple", 0.45,
        [35574, 35836, 35843, 35920, 35977, 36056, 36259, 37297]),
    "retriever and vector store integrations": (
        "simple", 0.45,
        [36547, 36745, 36753, 37046, 38058, 38186, 38203, 38212]),
    "token counting and usage metadata": (
        "simple", 0.36,
        [35558, 36661, 37373, 37754, 37815, 38186, 38229, 38249]),
    "streaming behavior and chunk handling": (
        "simple", 0.27,
        [35436, 35442, 35514, 36809, 37421, 37869, 38034, 38226]),
    "prompt templates and output parsers": (
        "simple", 0.18,
        [35727, 36603, 36606, 37358, 38103, 38159, 38193, 38209]),
    "tool calling and function calling": (
        "ambiguous", 0.82,
        [35514, 35766, 35836, 36441, 36679, 37093, 37195, 37426]),
    "performance and latency": (
        "ambiguous", 0.82,
        [35783, 35836, 36126, 36488, 36835, 37754, 37972, 38058]),
    "developer experience": (
        "ambiguous", 0.55,
        [35836, 35842, 36297, 36310, 36373, 37701, 37938, 38170]),
    "documentation gaps": (
        "adversarial", 0.82,
        [35514, 35836, 36067, 36211, 36214, 37018, 37452, 38226]),
    # Not in the overlap probe. Baseline derived from its finding, which cited
    # 8/8 — so the cited set IS the retrieved set. Different process
    # invocation, which makes it a cross-run determinism check.
    "xylophone quarterly banana": (
        "adversarial", None,
        [35442, 36809, 36889, 37754, 37878, 38226, 38229, 38243]),
}

# Completeness enumerates themes from retrieval; correct refusal has no
# referent on that dimension. Exempt, per the logged PRD.md override.
COMPLETENESS_EXEMPT = {"documentation gaps"}

with open(FINDINGS_IN, encoding="utf-8") as f:
    raw_findings = json.load(f)

sha = subprocess.run(
    ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()
dirty = bool(subprocess.run(
    ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
).stdout.strip())

scenarios, failures = [], []

for topic, (band, overlap, expected) in SCENARIOS.items():
    print(f"--- {topic}")

    recs = query(topic, k=K)
    got = sorted(r["number"] for r in recs)
    assert got == sorted(expected), (
        f"RETRIEVAL DRIFT on '{topic}'.\n"
        f"  expected: {sorted(expected)}\n"
        f"  got:      {got}\n"
        f"Fixture capture halted — retrieval is not reproducible."
    )
    print(f"    retrieval verified: {got}")

    finding = DiscoveryFinding(**raw_findings[topic])
    try:
        prd = draft_prd(finding)
    except Exception as exc:
        print(f"    !! draft_prd failed: {type(exc).__name__}: {exc}")
        failures.append((topic, f"{type(exc).__name__}: {exc}"))
        continue

    print(f"    PRD drafted: {len(prd.user_stories)} stories, "
          f"{len(prd.acceptance_criteria)} ACs, {len(prd.risks)} risks")

    scenarios.append({
        "topic": topic,
        "band": band,
        "overlap_score": overlap,
        "completeness_exempt": topic in COMPLETENESS_EXEMPT,
        "finding": finding.model_dump(),
        "retrieved_issues": [
            {"number": r["number"], "url": r["url"], "labels": r["labels"],
             "distance": r["distance"], "document": r["document"]}
            for r in recs
        ],
        "prd": prd.model_dump(),
    })

fixture = {
    "provenance": {
        "commit": sha,
        "working_tree_dirty": dirty,
        "agent_model": config.AGENT_MODEL,
        "embedding_model": config.EMBEDDING_MODEL,
        "retrieval_k": K,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    },
    "scenarios": scenarios,
}

os.makedirs("evals", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(fixture, f, indent=2)

print("\n" + "=" * 70)
print(f"captured {len(scenarios)}/{len(SCENARIOS)} scenarios -> {OUT}")
if failures:
    print("FAILURES:")
    for topic, err in failures:
        print(f"  {topic}: {err}")
if dirty:
    print("WARNING: working tree dirty — provenance commit is approximate.")
