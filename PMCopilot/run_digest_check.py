"""Characterization: re-run ONE audience N times against the PERSISTED
roadmap (input held constant) and report key_claims counts."""
import sys
import json
from pathlib import Path
from schemas.prd import PRD
from schemas.roadmap import RoadmapItem
from agents.summarizer import summarize

AUDIENCE = sys.argv[1] if len(sys.argv) > 1 else "eng"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 2
OUT = Path("data/output")
THEMES = ["streaming", "authentication", "tool_calling"]

prds = [
    PRD.model_validate_json((OUT / f"prd_{t}.json").read_text(encoding="utf-8"))
    for t in THEMES
]
roadmap = [
    RoadmapItem.model_validate(x)
    for x in json.loads((OUT / "roadmap.json").read_text(encoding="utf-8"))
]

draws = OUT / "sonnet5_draws"
draws.mkdir(parents=True, exist_ok=True)

for run in range(1, N + 1):
    d = summarize(prds, roadmap, AUDIENCE)
    path = draws / f"digest_{AUDIENCE}_run{run}.json"
    path.write_text(d.model_dump_json(indent=2), encoding="utf-8")
    print(f"run {run}: key_claims={len(d.key_claims)} -> {path}")
    for c in d.key_claims:
        print(f"   - {c.text[:80]}  {c.grounded_in}")
