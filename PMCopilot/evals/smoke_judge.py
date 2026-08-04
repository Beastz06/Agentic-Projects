"""Smoke: judge one scenario on all four dimensions before spending 40 calls."""
import json
from evals.judge import judge, JUDGE_MODEL

TARGET = "authentication"

with open("evals/fixture_v1.json", encoding="utf-8") as f:
    fixture = json.load(f)

sc = next(s for s in fixture["scenarios"] if s["topic"] == TARGET)
print(f"judging '{TARGET}' with {JUDGE_MODEL}\n")

for dim in ("hallucination", "grounding", "completeness", "ac_quality"):
    result, attempts = judge(
        dim,
        prd=sc["prd"],
        finding=sc["finding"],
        retrieved_issues=sc["retrieved_issues"],
    )
    print("=" * 70)
    print(f"{dim.upper()}  score={result.score}  attempts={attempts}")
    print("-" * 70)
    print("findings:")
    print(json.dumps(result.findings, indent=2)[:2500])
    print("\nrationale:")
    print(result.rationale)
    print()
