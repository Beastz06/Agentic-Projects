"""Probe: run Discovery across candidate eval topics (C9 scenario selection).

Acceptance rule, FIXED BEFORE RUNNING:
  simple-band candidate requires >= 5 of 8 retrieved issues cited.
Failing is reassignment (thin-evidence adversarial slot), not discard.

Findings are dumped to evals/candidate_findings.json and are intended to
serve as the fixture's source_findings — same commit, same model.
"""
import json
import os
from agents.discovery import research, RETRIEVAL_K

FLOOR = 5
OUT = "evals/candidate_findings.json"

CANDIDATES = [
    "authentication",
    "token counting and usage metadata",
    "streaming behavior and chunk handling",
    "retriever and vector store integrations",
    "document loaders and text splitters",
    "prompt templates and output parsers",
    "tool calling and function calling",
    "developer experience",
    "error handling and debuggability",
    "performance and latency",
    "backward compatibility and breaking changes",
    "documentation gaps",
    "xylophone quarterly banana",
]

os.makedirs("evals", exist_ok=True)
results, rows = {}, []

for topic in CANDIDATES:
    try:
        finding = research(topic)
    except Exception as exc:
        print(f"!! {topic}: {type(exc).__name__}: {exc}")
        rows.append((topic, None, None, f"ERROR {type(exc).__name__}"))
        continue

    cited = set()
    for pp in finding.pain_points:
        cited.update(pp.evidence_issue_ids)

    results[topic] = finding.model_dump()
    verdict = "PASS" if len(cited) >= FLOOR else "FAIL"
    rows.append((topic, len(finding.pain_points), len(cited), verdict))

    print(f"=== {topic}")
    print(f"    pain_points: {len(finding.pain_points)}   "
          f"cited: {len(cited)}/{RETRIEVAL_K}   {verdict}")
    for pp in finding.pain_points:
        print(f"    [{pp.severity:>6}] ids={pp.evidence_issue_ids}")
        print(f"             {pp.cluster}")
    print(f"    seed: {finding.suggested_prd_seed}\n")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("=" * 70)
print(f"SUMMARY  (floor: >= {FLOOR} of {RETRIEVAL_K} cited)")
print("=" * 70)
for topic, npp, ncited, verdict in rows:
    pp = "  -" if npp is None else f"{npp:>3}"
    ci = "  -" if ncited is None else f"{ncited:>3}"
    print(f"  {verdict:<16} pp={pp}  cited={ci}   {topic}")
print(f"\nwrote {OUT}")
