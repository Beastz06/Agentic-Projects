"""End-to-end slice: Discovery (C2) -> PRD Drafter (C3) -> JSON artifact."""
import sys
from pathlib import Path
from agents.discovery import research
from agents.prd_drafter import draft_prd

THEME = sys.argv[1] if len(sys.argv) > 1 else "authentication"
RUN_ID = sys.argv[2] if len(sys.argv) > 2 else None
OUT = Path("data/output")

finding = research(THEME)
print(f"Discovery: {len(finding.pain_points)} pain points for '{THEME}'")

prd = draft_prd(finding)
print(f"PRD: {len(prd.user_stories)} stories, {len(prd.acceptance_criteria)} ACs")

if RUN_ID is None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"prd_{THEME}.json"
else:
    draws_dir = OUT / "sonnet5_draws"
    draws_dir.mkdir(parents=True, exist_ok=True)
    path = draws_dir / f"prd_{THEME}_run{RUN_ID}.json"

path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")
print(f"Saved: {path}")
