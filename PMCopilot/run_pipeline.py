"""End-to-end slice: Discovery (C2) -> PRD Drafter (C3) -> JSON artifact."""
from pathlib import Path
from agents.discovery import research
from agents.prd_drafter import draft_prd

THEME = "authentication"
OUT = Path("data/output")

finding = research(THEME)
print(f"Discovery: {len(finding.pain_points)} pain points for '{THEME}'")

prd = draft_prd(finding)
print(f"PRD: {len(prd.user_stories)} stories, {len(prd.acceptance_criteria)} ACs")

OUT.mkdir(parents=True, exist_ok=True)
path = OUT / f"prd_{THEME}.json"
path.write_text(prd.model_dump_json(indent=2), encoding="utf-8")
print(f"Saved: {path}")