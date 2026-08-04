"""Run the C9 judge over the frozen fixture and persist scored results.

BASELINE RUN. Defects the judge surfaces are recorded, not fixed, before this
completes -- fixing first and publishing only the repaired numbers fits the
system to its own test. The cycle is measure / fix / measure, and the delta
between v1 and v2 is the artifact.

Results are written after every scenario. Forty Opus calls is long enough that
a mid-run failure should not discard completed work.
"""
import json
from datetime import datetime, timezone
from evals.judge import judge, JUDGE_MODEL
from evals.rubrics import DIMENSIONS

FIXTURE = "evals/fixture_v1.json"
OUT = "evals/results_v1.json"

# From PRD.md. Held here as data so the summary reports against the committed
# claim rather than against whatever the numbers happen to be.
TARGETS = {
    "hallucination": {"mean": 5.0, "floor": 5, "text": "all score 5 (mean 5.0, zero below 5)"},
    "grounding": {"mean": 5.0, "floor": 5, "text": "all score 5 (mean 5.0, zero below 5)"},
    "completeness": {"mean": 4.0, "floor": None, "text": "mean >= 4.0"},
    "ac_quality": {"mean": 4.5, "floor": None, "text": "mean >= 4.5"},
}


def write(results: dict) -> None:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


with open(FIXTURE, encoding="utf-8") as f:
    fixture = json.load(f)

results = {
    "provenance": {
        # What produced the PRDs. Carried through from the fixture so a score
        # is never separated from the code that generated its subject.
        "fixture_commit": fixture["provenance"]["commit"],
        "fixture_captured_at": fixture["provenance"]["captured_at"],
        "agent_model": fixture["provenance"]["agent_model"],
        "retrieval_k": fixture["provenance"]["retrieval_k"],
        # What produced the scores. Deliberately a different tier from the
        # drafter: a fabrication the drafter found plausible is plausible to
        # that model. Recorded so a cross-model re-judge has a baseline.
        "judge_model": JUDGE_MODEL,
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "temperature_pinned": False,  # Opus 5 rejects the parameter
    },
    "scenarios": [],
    "errors": [],
}

for sc in fixture["scenarios"]:
    topic = sc["topic"]
    print(f"--- {topic} [{sc['band']}]")
    scored = {
        "topic": topic,
        "band": sc["band"],
        "overlap_score": sc["overlap_score"],
        "completeness_exempt": sc["completeness_exempt"],
        "dimensions": {},
    }

    for dim in DIMENSIONS:
        if dim == "completeness" and sc["completeness_exempt"]:
            # Correct refusal has no theme set to be complete against, so the
            # dimension has no referent here. Exempt, not zero -- scoring it
            # straight would admit a measurement of a different property into
            # the mean. Logged override against PRD.md's "across 10 scenarios".
            scored["dimensions"][dim] = {
                "score": None,
                "exempt": True,
                "reason": "correct refusal -- no enumerable themes to cover",
            }
            print(f"    {dim:<14} EXEMPT")
            continue

        try:
            result, attempts = judge(
                dim,
                prd=sc["prd"],
                finding=sc["finding"],
                retrieved_issues=sc["retrieved_issues"],
            )
        except Exception as exc:
            print(f"    {dim:<14} !! {type(exc).__name__}: {exc}")
            results["errors"].append(
                {"topic": topic, "dimension": dim,
                 "error": f"{type(exc).__name__}: {exc}"}
            )
            scored["dimensions"][dim] = {"score": None, "error": True}
            continue

        scored["dimensions"][dim] = {
            "score": result.score,
            "attempts": attempts,
            "findings": result.findings,
            "rationale": result.rationale,
        }
        flag = "" if attempts == 1 else f"  (repaired x{attempts - 1})"
        print(f"    {dim:<14} {result.score}{flag}")

    results["scenarios"].append(scored)
    write(results)

# ---------------------------------------------------------------- summary

summary = {}
for dim in DIMENSIONS:
    scores = [
        s["dimensions"][dim]["score"]
        for s in results["scenarios"]
        if s["dimensions"].get(dim, {}).get("score") is not None
    ]
    if not scores:
        summary[dim] = {"n": 0}
        continue
    target = TARGETS[dim]
    mean = sum(scores) / len(scores)
    below = [s for s in scores if s < target["mean"]]
    meets = mean >= target["mean"] and (
        target["floor"] is None or min(scores) >= target["floor"]
    )
    summary[dim] = {
        "n": len(scores),
        "mean": round(mean, 2),
        "min": min(scores),
        "max": max(scores),
        "scores": scores,
        "target": target["text"],
        "meets_target": meets,
        "n_below_target": len(below),
    }

results["summary"] = summary
write(results)

print("\n" + "=" * 74)
print(f"SUMMARY  (fixture {results['provenance']['fixture_commit'][:7]}, "
      f"judge {JUDGE_MODEL})")
print("=" * 74)
print(f"{'dimension':<16}{'n':>3}{'mean':>7}{'min':>5}{'max':>5}   "
      f"{'target':<34}")
print("-" * 74)
for dim in DIMENSIONS:
    s = summary[dim]
    if not s["n"]:
        print(f"{dim:<16}  0     --   --   --   no scores")
        continue
    verdict = "MEETS" if s["meets_target"] else "MISSES"
    print(f"{dim:<16}{s['n']:>3}{s['mean']:>7.2f}{s['min']:>5}{s['max']:>5}   "
          f"{s['target']:<34}{verdict}")

print("\nper-scenario scores:")
head = f"{'scenario':<44}{'band':<13}"
for dim in DIMENSIONS:
    head += f"{dim[:5]:>7}"
print(head)
print("-" * 74)
for s in results["scenarios"]:
    row = f"{s['topic'][:43]:<44}{s['band']:<13}"
    for dim in DIMENSIONS:
        v = s["dimensions"].get(dim, {}).get("score")
        row += f"{'exempt' if v is None else v:>7}"
    print(row)

if results["errors"]:
    print(f"\nERRORS ({len(results['errors'])}):")
    for e in results["errors"]:
        print(f"  {e['topic']} / {e['dimension']}: {e['error']}")

print(f"\nwrote {OUT}")
