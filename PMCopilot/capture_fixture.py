"""Capture the C9 eval fixture: 10 scenarios, frozen at one commit.

Fixture unit is FROZEN, not live: the judge is the only moving part during
Day 32 rubric tuning, so a score change has exactly one possible cause.

retrieved_issues is carried forward from a prior fixture rather than re-queried.
The index is approximate and the rank-8 boundary gap on this corpus is ~0.003
against a band width of ~0.13, so live retrieval returns a different eighth
issue often enough to halt a capture mid-run. Carrying the set forward makes
retrieval exactly reproducible and leaves the drafter prompt as the only thing
that differs between fixtures — which is what the comparison requires. The
assertion still runs, but it now checks that the source fixture is the expected
one, not that retrieval is stable.
"""
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
import config
import telemetry
import argparse
from schemas.discovery import DiscoveryFinding
from agents.prd_drafter import draft_prd

K = 8
FINDINGS_IN = "evals/candidate_findings.json"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", required=True,
                    help="path to write the fixture (e.g. evals/fixture_v2.json)")
parser.add_argument("--from-fixture", required=True,
                    help="fixture whose retrieved_issues to reuse, e.g. evals/fixture_v2.json")
args = parser.parse_args()
OUT = args.out

if os.path.exists(OUT):
    raise SystemExit(
        f"{OUT} already exists. A fixture is the frozen subject of every score "
        f"that cites it; overwriting one in place makes those scores "
        f"unreproducible. Choose a new path or move the existing file."
    )

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

with open(args.from_fixture, encoding="utf-8") as f:
    source = json.load(f)
SOURCE_ISSUES = {s["topic"]: s["retrieved_issues"] for s in source["scenarios"]}

sha = subprocess.run(
    ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()
dirty = bool(subprocess.run(
    ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
).stdout.strip())

scenarios, failures = [], []

events: list[dict] = []
handler = telemetry.TelemetryHandler(events)
root_log = logging.getLogger(telemetry.ROOT)
root_log.addHandler(handler)
root_log.setLevel(logging.INFO)

for topic, (band, overlap, expected) in SCENARIOS.items():
    print(f"--- {topic}")

    recs = SOURCE_ISSUES[topic]
    got = sorted(r["number"] for r in recs)
    assert got == sorted(expected), (
        f"SOURCE FIXTURE MISMATCH on '{topic}'.\n"
        f"  expected: {sorted(expected)}\n"
        f"  got:      {got}\n"
        f"The fixture passed to --from-fixture does not carry the retrieval "
        f"this capture expects."
    )
    print(f"    retrieval carried forward: {got}")

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
        "retrieval_source": args.from_fixture,
        "retrieval_source_commit": source["provenance"]["commit"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    },
    "scenarios": scenarios,
    "telemetry": events,
}

os.makedirs("evals", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(fixture, f, indent=2)

print("\n" + "=" * 70)
print(f"captured {len(scenarios)}/{len(SCENARIOS)} scenarios -> {OUT}")

first_attempts = [
    e for e in events
    if e.get("pmc_event") == telemetry.EVENT_MODEL_CALL and e.get("pmc_attempt") == 1
]
# Every theme that reaches draft_prd emits an attempt-1 record: the emit sits
# before the parse, so exhausting the retry budget still leaves one behind.
# Failures are NOT subtracted. The only theme that emits nothing is one where
# create() itself raised, and that is the failed-call gap -- which this check
# should surface, not absorb.
expected = len(SCENARIOS)

if len(first_attempts) != expected:
    by_logger: dict[str, int] = {}
    for e in first_attempts:
        by_logger[e["logger"]] = by_logger.get(e["logger"], 0) + 1
    raise SystemExit(
        f"TELEMETRY RECONCILIATION FAILED: expected {expected} first-attempt "
        f"model calls, collected {len(first_attempts)}.\n"
        f"  by logger: {by_logger or '(none)'}\n"
        f"Capture is written to {OUT}; its telemetry is incomplete and any "
        f"cost figure derived from it would understate the run."
    )

print(f"telemetry: {len(first_attempts)} first-attempt calls, "
      f"{len(events)} records total")

if failures:
    print("FAILURES:")
    for topic, err in failures:
        print(f"  {topic}: {err}")
if dirty:
    print("WARNING: working tree dirty — provenance commit is approximate.")
